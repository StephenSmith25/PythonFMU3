cd ..
mkdir tmp-build
cd tmp-build
cmake ../pythonfmu3/pythonfmu-export -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
cd ..
rmdir /s /q tmp-build
cd docker