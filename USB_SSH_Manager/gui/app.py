import tkinter as tk
from tkinter import ttk, scrolledtext
from core.tunnel import TunnelManager
from core.executor import CommandExecutor

class USBManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB SSH Device Manager")
        self.root.geometry("700x500")
        
        # Apply dark mode theme roughly
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.entry_bg = "#3c3c3c"
        self.entry_fg = "#d4d4d4"
        
        self.root.configure(bg=self.bg_color)
        
        self.tunnel_manager = TunnelManager()
        self.executor = CommandExecutor()
        
        self.build_ui()
        
    def build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TButton', background='#3a3d41', foreground=self.fg_color, padding=5)
        style.map('TButton', background=[('active', '#505357')])
        style.configure('TLabelframe', background=self.bg_color, foreground=self.fg_color)
        style.configure('TLabelframe.Label', background=self.bg_color, foreground=self.fg_color)
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Config Panel ---
        config_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Host/Port
        ttk.Label(config_frame, text="IP Address:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.ip_var = tk.StringVar(value="localhost")
        ip_entry = tk.Entry(config_frame, textvariable=self.ip_var, bg=self.entry_bg, fg=self.entry_fg, insertbackground=self.fg_color)
        ip_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(config_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar(value="2222")
        port_entry = tk.Entry(config_frame, textvariable=self.port_var, bg=self.entry_bg, fg=self.entry_fg, insertbackground=self.fg_color, width=10)
        port_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Credentials
        ttk.Label(config_frame, text="Username:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.user_var = tk.StringVar(value="root")
        user_entry = tk.Entry(config_frame, textvariable=self.user_var, bg=self.entry_bg, fg=self.entry_fg, insertbackground=self.fg_color)
        user_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(config_frame, text="Password:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.pass_var = tk.StringVar(value="alpine")
        pass_entry = tk.Entry(config_frame, textvariable=self.pass_var, show="*", bg=self.entry_bg, fg=self.entry_fg, insertbackground=self.fg_color)
        pass_entry.grid(row=1, column=3, sticky=tk.EW, padx=5, pady=5)
        
        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(3, weight=1)
        
        # --- Control Panel ---
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.tunnel_btn = ttk.Button(control_frame, text="Establish Tunnel (iproxy)", command=self.toggle_tunnel)
        self.tunnel_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.diag_btn = ttk.Button(control_frame, text="Execute Diagnostics", command=self.run_diagnostics)
        self.diag_btn.pack(side=tk.LEFT)
        
        # --- Log Panel ---
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg="#2d2d2d", fg="#d4d4d4", font=("Consolas", 10), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message):
        self.root.after(0, self._append_log, message)
        
    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def toggle_tunnel(self):
        if self.tunnel_manager.running:
            self.tunnel_manager.stop_tunnel(self.log)
            self.tunnel_btn.config(text="Establish Tunnel (iproxy)")
        else:
            self.tunnel_manager.start_tunnel(local_port=self.port_var.get(), remote_port=22, log_callback=self.log)
            self.tunnel_btn.config(text="Stop Tunnel")
            
    def run_diagnostics(self):
        self.diag_btn.config(state=tk.DISABLED)
        self.log("\n--- Starting Diagnostics ---\n")
        
        def on_complete():
            self.root.after(0, lambda: self.diag_btn.config(state=tk.NORMAL))
            self.log("--- Diagnostics Complete ---\n")
            
        self.executor.run_diagnostics(
            host=self.ip_var.get(),
            port=self.port_var.get(),
            username=self.user_var.get(),
            password=self.pass_var.get(),
            log_callback=self.log,
            completion_callback=on_complete
        )

    def on_closing(self):
        self.tunnel_manager.stop_tunnel()
        self.root.destroy()
