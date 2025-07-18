cd ..
podman build -f docker/DockerFile -t pythonfmubuilder --target build .
podman run --name pythonfmubuilder pythonfmubuilder
podman cp pythonfmubuilder:/pythonfmu3/resources/ pythonfmu3
podman rm pythonfmubuilder
cd docker