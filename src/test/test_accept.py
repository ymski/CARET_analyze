import os
from caret_analyze import Architecture, Lttng, Application


def test_accept():
    # trace_data = os.path.expanduser('./session-20240417161654')
    trace_data = os.path.expanduser('/home/yamasaki/src/caret/analyze_script/warning/session-20231114050140')
    # trace_data = os.path.expanduser('/home/yamasaki/src/caret/analyze_script/warning/session-20240417161654')

    # lttng = Lttng(trace_data, force_conversion=False)
    # arch = Architecture('lttng', trace_data)
    # arch.export('arch_from_lttng.yaml', force=True)

    # print('create app from Lttng')
    # app = Application(arch, lttng)


    # print('Load arch from yaml')
    # arch_from_yaml = Architecture('yaml', 'arch_from_lttng.yaml')
    # arch_from_yaml.export('arch_from_arch.yaml')

    # print('create app from yaml')
    # app_from_yaml = Application(arch_from_yaml, lttng)

    lttng = Lttng(trace_data, force_conversion=False)
    arch = Architecture('yaml', './arch.yaml')

    app = Application(arch, lttng)
    app.get_path("component_sensing_0")
