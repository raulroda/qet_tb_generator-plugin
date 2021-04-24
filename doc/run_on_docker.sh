#!/bin/sh

# El contenedor ejecuta run.sh al iniciarse.
# Puede pasarse como argumento un esquema eléctrico. En caso contrario se muestra diálogo
# para seleccionar archivo.

xhost +

sudo docker run -it --rm \
--volume "$PWD":/usr/src/app \
--volume /tmp/.X11-unix:/tmp/.X11-unix \
-w /usr/src/app \
--env DISPLAY=$DISPLAY \
qet_tb $1