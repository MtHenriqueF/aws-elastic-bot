import boto3
import sys

# Configuração Básica
REGION = 'us-east-1'
ec2 = boto3.client('ec2', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)

def get_latest_ami():
    print("🔍 Buscando a imagem (AMI) mais recente do Amazon Linux 2023...")
    response = ssm.get_parameter(
        Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64'
    )
    ami_id = response['Parameter']['Value']
    print(f"   ✅ AMI encontrada: {ami_id}")
    return ami_id

def create_instance():
    ami_id = get_latest_ami()
    
    print("\n🚀 Iniciando criação da instância EC2 (t3.micro)...")
    try:
        instances = ec2.run_instances(
            ImageId=ami_id,
            InstanceType='t3.micro',
            MinCount=1,
            MaxCount=1
        )
        instance_id = instances['Instances'][0]['InstanceId']
        print(f"   ✅ Sucesso! Instância criada: {instance_id}")
        print("   (Lembre-se de destruir essa máquina depois para não gerar custos!)")
        return instance_id
    except Exception as e:
        print(f"   ❌ Erro ao criar instância: {e}")
        sys.exit(1)

if __name__ == '__main__':
    create_instance()