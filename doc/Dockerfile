# Crea una maquina con todo lo necesario la programamción del plugin de generación
# de Borneros de QElectrotech
#
# Desde el directorio del proyecto:
# IMAGEN: sudo docker build -t qettb .
# EJECUTAR: sudo docker run -it --rm  -v "$PWD":/usr/src/app -w /usr/src/app qettb ls


#FROM python:3.5.6-alpine
FROM python:3.6
MAINTAINER raulroda8@gmail.com

RUN apt update \
 && apt -y install python3-tk \
 && apt -y install twine \
 && python3 -m pip install setuptools pyinstaller\
 && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

# Entrypoint no se puede sobreescribit
#ENTRYPOINT ["/usr/src/app/run.sh"]
CMD ["/usr/src/app/run.sh"]
# Para ejecutar pasando un diagrama como parametro: 
#   sh run_on_docker.sh "./run.sh sample_projects/THERMO_v0.7.qet"
