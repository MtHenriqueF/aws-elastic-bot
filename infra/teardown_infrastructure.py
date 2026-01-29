import boto3
import time

# Configuração
REGION = 'us-east-1'
PROJECT_NAME = 'aws-elastic-bot'

# Clientes
ec2 = boto3.client('ec2', region_name=REGION)
elbv2 = boto3.client('elbv2', region_name=REGION)
autoscaling = boto3.client('autoscaling', region_name=REGION)

def delete_auto_scaling_group():
    asg_name = f"{PROJECT_NAME}-asg"
    print(f"🔥 Deletando Auto Scaling Group: {asg_name}...")
    try:
        # Force delete termina as instâncias automaticamente
        autoscaling.delete_auto_scaling_group(AutoScalingGroupName=asg_name, ForceDelete=True)
        print("   ⏳ Aguardando ASG terminar as instâncias (pode levar 2-3 mins)...")
        
        # Loop simples para esperar o ASG sumir
        while True:
            try:
                response = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
                if not response['AutoScalingGroups']:
                    break
                # Se estiver 'Deleting', esperamos
                status = response['AutoScalingGroups'][0]['Status'] if 'Status' in response['AutoScalingGroups'][0] else 'Deleting'
                print(f"   ... status: {status}")
                time.sleep(15)
            except:
                break # Se der erro de não encontrado, é porque sumiu
        print("   ✅ ASG deletado.")
    except Exception as e:
        print(f"   ⚠️  Erro ou já deletado: {e}")

def delete_launch_template():
    lt_name = f"{PROJECT_NAME}-lt"
    print(f"📄 Deletando Launch Template: {lt_name}...")
    try:
        ec2.delete_launch_template(LaunchTemplateName=lt_name)
        print("   ✅ Launch Template deletado.")
    except Exception as e:
        print(f"   ⚠️  {e}")

def delete_load_balancer():
    lb_name = f"{PROJECT_NAME}-alb"
    print(f"⚖️  Buscando e deletando Load Balancer: {lb_name}...")
    try:
        lbs = elbv2.describe_load_balancers(Names=[lb_name])
        lb_arn = lbs['LoadBalancers'][0]['LoadBalancerArn']
        elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
        print("   ⏳ Aguardando exclusão do ELB...")
        waiter = elbv2.get_waiter('load_balancers_deleted')
        waiter.wait(Names=[lb_name])
        print("   ✅ Load Balancer deletado.")
    except Exception as e:
        print(f"   ⚠️  {e}")

def delete_target_group():
    tg_name = f"{PROJECT_NAME}-tg"
    print(f"🎯 Buscando e deletando Target Group: {tg_name}...")
    try:
        tgs = elbv2.describe_target_groups(Names=[tg_name])
        tg_arn = tgs['TargetGroups'][0]['TargetGroupArn']
        elbv2.delete_target_group(TargetGroupArn=tg_arn)
        print("   ✅ Target Group deletado.")
    except Exception as e:
        print(f"   ⚠️  {e}")

def delete_security_group():
    sg_name = f"{PROJECT_NAME}-sg"
    print(f"🛡️  Deletando Security Group: {sg_name}...")
    try:
        # Precisamos esperar um pouco pois a AWS demora a liberar o vínculo do SG com o ELB deletado
        time.sleep(5) 
        ec2.delete_security_group(GroupName=sg_name)
        print("   ✅ Security Group deletado.")
    except Exception as e:
        print(f"   ❌ Erro (provavelmente dependência ainda ativa, tente rodar de novo em 1 min): {e}")

def teardown():
    print("🚨 INICIANDO DESTRUIÇÃO DA INFRAESTRUTURA 🚨")
    delete_auto_scaling_group()
    delete_launch_template()
    delete_load_balancer()
    delete_target_group()
    delete_security_group()
    print("\n🏁 Limpeza concluída!")

if __name__ == '__main__':
    teardown()