import sys
import os
import traceback

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect stderr to a crash log file so we can see any errors
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
sys.stderr = open(log_path, "w")

try:
    import tkinter as tk
    from gui.app import USBManagerApp

    def main():
        root = tk.Tk()
        app = USBManagerApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()

    if __name__ == "__main__":
        main()

except Exception as e:
    sys.stderr.write(f"FATAL ERROR: {e}\n")
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
finally:
    sys.stderr.flush()
