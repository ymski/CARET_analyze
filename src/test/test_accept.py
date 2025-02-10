from caret_analyze import Architecture, Application, check_procedure, Lttng, LttngEventFilter

class TestAccept:
    def test_accept(self):
        tracing_log_path = '/home/yamasaki/data/trace/xx1047'
        lttng =Lttng(tracing_log_path)
