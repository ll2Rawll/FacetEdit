"""Dispose dialog variables and traces on their owning Tk thread.

Variable traces can retain a whole dialog through callback cycles. Leaving their
cleanup to Python's collector can run Tk finalizers in a geometry/file worker.
Keep explicit ownership until the dialog closes, including direct destruction.
"""
import tkinter as tk


class DialogState:
    def __init__(self, window):
        self.window = window
        self.variables = []
        self.cleanups = []
        window.bind('<Destroy>', self._destroy, add='+')

    def string(self, value=''):
        variable = tk.StringVar(master=self.window, value=value)
        self.variables.append(variable)
        return variable

    def boolean(self, value=False):
        variable = tk.BooleanVar(master=self.window, value=value)
        self.variables.append(variable)
        return variable

    def release(self, variable):
        # Remove traces before unsetting; callbacks must not run during teardown.
        for mode, name in variable.trace_info():
            variable.trace_remove(mode, name)
        variable.__del__()
        # Tk's own finalizer returns immediately when _tk is None. Detach the
        # interpreter/root so retained automation handles are harmless to GC.
        variable._tk = None
        variable._root = None
        self.variables.remove(variable)

    def _destroy(self, event):
        if event.widget is not self.window:
            return
        try:
            for cleanup in self.cleanups:
                cleanup()
        finally:
            for variable in self.variables[:]:
                self.release(variable)
            self.cleanups.clear()
            self.window = None
