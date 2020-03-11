import imp
import subprocess
import os
from string import Template

PLUGINS = [
    'interpolate',
]

BASE_FOLDER = 'torch2trt/converters'

NINJA_TEMPLATE = Template((
    "rule link\n"
    "  command = g++ -shared -o $$out $$in -L$torch_dir/lib -L$cuda_dir/lib64 -L$trt_lib_dir -lc10 -lc10_cuda -ltorch -lcudart -lprotobuf -lprotobuf-lite -pthread -lpthread -lnvinfer\n"
    "rule protoc\n"
    "  command = protoc $$in --cpp_out=. --python_out=.\n"
    "rule cxx\n"
    "  command = g++ -c -fPIC $$in -I$cuda_dir/include -I$torch_dir/include -I$torch_dir/include/torch/csrc/api/include -I. -std=c++11 -I$trt_inc_dir\n"
))

PLUGIN_TEMPLATE = Template((
    "build $plugin_dir/$plugin.pb.h $plugin_dir/$plugin.pb.cc $plugin_dir/${plugin}_pb2.py: protoc $plugin_dir/$plugin.proto\n"
    "build $plugin.pb.o: cxx $plugin_dir/$plugin.pb.cc\n"
    "build $plugin.o: cxx $plugin_dir/$plugin.cpp\n"
))


def get_subdirs(path):
    return next(os.walk(path))[1]


def infer_arch():
    dirs = get_subdirs('/usr/lib')
    acceptable = ['x86_64-linux-gnu', 'aarch64-linux-gnu']
    for name in acceptable:
        if name in dirs:
            return name
    raise RuntimeError('Failed to automatically  determine arch path, use flags to define it')


def build(cuda_dir="/usr/local/cuda",
          torch_dir=imp.find_module('torch')[1],
          trt_inc_dir=None,
          trt_lib_dir=None):

    if trt_lib_dir is None:
        trt_lib_dir = os.path.join("/usr/lib", infer_arch())

    if trt_inc_dir is None:
        trt_inc_dir = os.path.join("/usr/include", infer_arch())

    global PLUGINS, BASE_FOLDER, NINJA_TEMPLATE, PLUGIN_TEMPLATE

    NINJA_STR = NINJA_TEMPLATE.substitute({
        'torch_dir': torch_dir,
        'cuda_dir': cuda_dir,
        'trt_inc_dir': trt_inc_dir,
        'trt_lib_dir': trt_lib_dir,
    })

    for pth in [trt_inc_dir, trt_lib_dir]:
        if not os.path.isdir(pth):
            raise RuntimeError('Required path does not exist: {}'.format(pth))

    plugin_o_files = []
    for plugin in PLUGINS:
        NINJA_STR += \
            PLUGIN_TEMPLATE.substitute({
                'plugin': plugin,
                'plugin_dir': os.path.join(BASE_FOLDER, plugin),
            })
        plugin_o_files += [plugin + '.pb.o', plugin + '.o']

    NINJA_STR += Template((
        "build torch2trt/libtorch2trt.so: link $o_files\n"
    )).substitute({'o_files': ' '.join(plugin_o_files)})

    with open('build.ninja', 'w') as f:
        f.write(NINJA_STR)

    res = subprocess.call(['ninja'])
    if res:
        raise RuntimeError('ninja returned with code: {}'.format(res))


if __name__ == '__main__':
    build()
