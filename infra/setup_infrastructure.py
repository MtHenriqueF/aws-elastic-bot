import boto3
import time
import sys
import base64

# Configuração
REGION = 'us-east-1'
PROJECT_NAME = 'aws-elastic-bot'

# Clientes AWS
ec2 = boto3.client('ec2', region_name=REGION)
elbv2 = boto3.client('elbv2', region_name=REGION)
autoscaling = boto3.client('autoscaling', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)

def get_vpc_and_subnets():
    print("🔍 Buscando VPC e Subnets padrão...")
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    subnet_ids = [s['SubnetId'] for s in subnets['Subnets']]
    return vpc_id, subnet_ids

def create_security_group(vpc_id):
    sg_name = f"{PROJECT_NAME}-sg"
    print(f"🛡️ Configurando Security Group: {sg_name}")
    try:
        sg = ec2.create_security_group(GroupName=sg_name, Description='Lab ELB ASG', VpcId=vpc_id)
        sg_id = sg['GroupId']
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}]
        )
        return sg_id
    except ec2.exceptions.ClientError as e:
        if 'Duplicate' in str(e):
            return ec2.describe_security_groups(GroupNames=[sg_name])['SecurityGroups'][0]['GroupId']
        raise

def deploy():
    vpc_id, subnet_ids = get_vpc_and_subnets()
    sg_id = create_security_group(vpc_id)

    # 1. Load Balancer
    print("⚖️ Criando Load Balancer (ELB)...")
    lb = elbv2.create_load_balancer(
        Name=f"{PROJECT_NAME}-alb", Subnets=subnet_ids, SecurityGroups=[sg_id], Scheme='internet-facing', Type='application', IpAddressType='ipv4'
    )
    lb_arn = lb['LoadBalancers'][0]['LoadBalancerArn']
    lb_dns = lb['LoadBalancers'][0]['DNSName']

    # 2. Target Group
    print("🎯 Criando Target Group...")
    tg = elbv2.create_target_group(
        Name=f"{PROJECT_NAME}-tg", Protocol='HTTP', Port=80, VpcId=vpc_id, TargetType='instance'
    )
    tg_arn = tg['TargetGroups'][0]['TargetGroupArn']
    
    # 3. Listener
    elbv2.create_listener(
        LoadBalancerArn=lb_arn, Protocol='HTTP', Port=80,
        DefaultActions=[{'Type': 'forward', 'TargetGroupArn': tg_arn}]
    )

    # 4. AMI & Launch Template
    ami_id = ssm.get_parameter(Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64')['Parameter']['Value']
    
    # Script de Boot (User Data) - Versão v3 (Docker + IMDSv2 + Meta Charset)
    user_data_script = """#!/bin/bash
    # 1. Instalação e Configuração do Docker
    yum update -y
    yum install -y docker
    systemctl start docker
    systemctl enable docker
    usermod -a -G docker ec2-user

    # 2. Resgate do ID de forma segura (Token IMDSv2)
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    EC2ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/instance-id)

    # 3. Criação da página HTML (COM CORREÇÃO DE CHARSET)
    mkdir -p /tmp/web
    # AQUI ESTÁ A CORREÇÃO:
    echo "<meta charset='UTF-8'>" > /tmp/web/index.html
    echo "<div style='text-align:center; margin-top:50px; font-family:sans-serif;'>" >> /tmp/web/index.html
    echo "<h1>🐳 Ola do DOCKER Container!</h1>" >> /tmp/web/index.html
    echo "<h3>Rodando na EC2: <span style='color:#007bff;'>$EC2ID</span></h3>" >> /tmp/web/index.html
    echo "<p>Infraestrutura atualizada automaticamente via <b>Boto3</b>.</p>" >> /tmp/web/index.html
    echo "</div>" >> /tmp/web/index.html

    # 4. Rodar o container Nginx
    docker run -d -p 80:80 -v /tmp/web/index.html:/usr/share/nginx/html/index.html nginx:latest
    """
    
    # ---------------------------------------------------------

    b64_user_data = base64.b64encode(user_data_script.encode('utf-8')).decode('ascii')

    print("📄 Criando Launch Template...")
    lt_name = f"{PROJECT_NAME}-lt"
    try:
        ec2.create_launch_template(
            LaunchTemplateName=lt_name,
            LaunchTemplateData={'ImageId': ami_id, 'InstanceType': 't3.micro', 'UserData': b64_user_data, 'SecurityGroupIds': [sg_id]}
        )
    except: pass # Já existe

    # 5. Auto Scaling Group
    print("📈 Criando Auto Scaling Group...")
    try:
        autoscaling.create_auto_scaling_group(
            AutoScalingGroupName=f"{PROJECT_NAME}-asg",
            LaunchTemplate={'LaunchTemplateName': lt_name, 'Version': '$Latest'},
            MinSize=1, MaxSize=3, DesiredCapacity=1,
            TargetGroupARNs=[tg_arn],
            VPCZoneIdentifier=','.join(subnet_ids)
        )
    except: pass # Já existe

    print(f"\n✅ INFRAESTRUTURA CRIADA COM SUCESSO!")
    print(f"🌍 Acesse aqui (pode demorar 2 mins): http://{lb_dns}")

if __name__ == '__main__':
    deploy()