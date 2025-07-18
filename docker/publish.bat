
cd ..
podman build -f docker/DockerFile -t pythonfmupublisher --target wheel .
podman run --name pythonfmupublisher pythonfmupublisher
podman cp pythonfmupublisher:/dist/ .
podman rm pythonfmupublisher
cd docker