import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import time
import os

class ZDrugMakerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Leo's Dilution Calculator and Volume Conversion Applet v1.1")
        self.geometry("1024x768")  # Increased window size
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.create_compound_name_frame()
        
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.create_estimate_drug_tab()
        self.create_calculate_vehicle_tab()
        self.create_perform_dilution_tab()
        self.create_bew_values_tab()
        self.create_output_tab()
        
        self.create_close_button()
        
    def create_compound_name_frame(self):
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        frame.columnconfigure(1, weight=1)
        
        ttk.Label(frame, text="Compound Name:").grid(row=0, column=0, sticky="w")
        self.compound_name = tk.StringVar()
        ttk.Entry(frame, textvariable=self.compound_name).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        ttk.Label(frame, text="Comments:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.comments = tk.Text(frame, height=3, wrap=tk.WORD)
        self.comments.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(5, 0))
        
    def create_close_button(self):
        close_button = ttk.Button(self, text="Close", command=self.quit)
        close_button.grid(row=2, column=0, pady=10)
        
    def create_estimate_drug_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Estimate Drug Amount")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)
        
        fields = [("BEW", "bew"), ("Dose (mg/kg)", "dose"), 
                  ("Avg Body Weight (g)", "avgbw"), ("Number of Animals", "animalnumber"),
                  ("Number of Trials", "trials")]
        
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=5)
            setattr(self, var_name, tk.DoubleVar())
            ttk.Entry(tab, textvariable=getattr(self, var_name)).grid(row=i, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Button(tab, text="Calculate", command=self.estimate_drug_amount).grid(row=len(fields), column=0, columnspan=2, pady=10)
        
        self.estimate_result = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("TkDefaultFont", 11))
        self.estimate_result.grid(row=0, column=2, rowspan=6, padx=10, pady=5, sticky="nsew")
        
    def create_calculate_vehicle_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Calculate Vehicle Amount")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(3, weight=1)
        
        fields = [("BEW", "vehicle_bew"), ("Dose (mg/kg)", "vehicle_dose"), 
                  ("Amount of drug weighed (mg)", "vehicle_amt")]
        
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=5)
            setattr(self, var_name, tk.DoubleVar())
            ttk.Entry(tab, textvariable=getattr(self, var_name)).grid(row=i, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Button(tab, text="Calculate", command=self.calculate_vehicle_amount).grid(row=len(fields), column=0, columnspan=2, pady=10)
        
        self.vehicle_result = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("TkDefaultFont", 11))
        self.vehicle_result.grid(row=0, column=2, rowspan=4, padx=10, pady=5, sticky="nsew")
        
    def create_perform_dilution_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Perform Dilution")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)
        
        fields = [("Volume of starting solution (ml)", "dilution_vol_tot_01"),
                  ("Concentration of starting solution (mg/ml)", "dilution_conc_01"),
                  ("Concentration of final solution (mg/ml)", "dilution_conc_02"),
                  ("Volume of new solution (ml)", "dilution_vol_02")]
        
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=5)
            setattr(self, var_name, tk.DoubleVar())
            ttk.Entry(tab, textvariable=getattr(self, var_name)).grid(row=i, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Button(tab, text="Calculate", command=self.perform_dilution).grid(row=len(fields), column=0, columnspan=2, pady=10)
        
        self.dilution_result = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("TkDefaultFont", 11))
        self.dilution_result.grid(row=0, column=2, rowspan=5, padx=10, pady=5, sticky="nsew")
        
    def create_bew_values_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="BEW Values")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        
        self.bew_values = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("TkDefaultFont", 11))
        self.bew_values.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.load_bew_values()
        
    def create_output_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Output")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("TkDefaultFont", 11))
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Add Export button
        export_button = ttk.Button(tab, text="Export", command=self.export_output)
        export_button.grid(row=1, column=0, pady=10)

    def export_output(self):
        # Get current timestamp
        timestamp = time.strftime('%Y%m%d_%H%M')
        
        # Get compound name
        compound_name = self.compound_name.get().strip()
        if not compound_name:
            messagebox.showerror("Export Error", "Please enter a compound name before exporting.")
            return
        
        # Create filename
        filename = f"{timestamp}_{compound_name}.txt"
        
        # Get output content
        content = self.output_text.get("1.0", tk.END)
        
        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=filename
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    file.write(content)
                messagebox.showinfo("Export Successful", f"Output exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"An error occurred while exporting: {str(e)}")


    def estimate_drug_amount(self):
        try:
            bew = self.bew.get()
            dose = self.dose.get()
            avgbw = self.avgbw.get()
            animalnumber = self.animalnumber.get()
            trials = self.trials.get()
            
            drugtot = bew * dose * 0.001 * avgbw * animalnumber * trials
            voltot01 = 1 * 0.001 * avgbw * animalnumber * trials
            voltot05 = 5 * 0.001 * avgbw * animalnumber * trials
            voltot10 = 10 * 0.001 * avgbw * animalnumber * trials
            
            result = f"Estimated Drug Amount and Volumes\n"
            result += f"{'='*40}\n"
            result += f"Compound: {self.compound_name.get()}\n"
            result += f"BEW: {bew:.3g}\n"
            result += f"Dose: {dose:.3g} mg/kg\n"
            result += f"{'='*40}\n"
            result += f"Drug amount needed: {drugtot:.3g} mg\n"
            result += f"{'='*40}\n"
            result += f"Volumes:\n"
            result += f"- Rats (1 ml/kg): {voltot01:.3g} ml\n"
            result += f"- Oral (5 ml/kg): {voltot05:.3g} ml\n"
            result += f"- Mice (10 ml/kg): {voltot10:.3g} ml\n"
            result += f"{'='*40}\n"
            
            self.estimate_result.delete(1.0, tk.END)
            self.estimate_result.insert(tk.END, result)
            
            self.update_output_tab("Estimate Drug Amount", result)
            self.log_calculation("Estimate Drug Amount", result)
            self.append_bew_to_file(self.compound_name.get(), bew)
            
        except tk.TclError:
            messagebox.showerror("Input Error", "Please enter valid numeric values.")
    
    def calculate_vehicle_amount(self):
        try:
            bew = self.vehicle_bew.get()
            dose = self.vehicle_dose.get()
            amt = self.vehicle_amt.get()
            
            vol_tot_01 = amt / (dose * bew)
            vol_tot_05 = (5 * amt) / (dose * bew)
            vol_tot_10 = (10 * amt) / (dose * bew)
            
            result = f"Vehicle Amounts for Different Concentrations\n"
            result += f"{'='*50}\n"
            result += f"Compound: {self.compound_name.get()}\n"
            result += f"BEW: {bew:.3g}\n"
            result += f"Dose: {dose:.3g} mg/kg\n"
            result += f"{'='*50}\n"
            result += f"Add {vol_tot_01:.3g} ml of vehicle to your {amt:.3g} mg of drug\n"
            result += f"to produce a 1ml/kg solution\n\n"
            result += f"Add {vol_tot_05:.3g} ml of vehicle to your {amt:.3g} mg of drug\n"
            result += f"to produce a 5ml/kg solution\n\n"
            result += f"Add {vol_tot_10:.3g} ml of vehicle to your {amt:.3g} mg of drug\n"
            result += f"to produce a 10ml/kg solution\n"
            result += f"{'='*50}\n"
            
            self.vehicle_result.delete(1.0, tk.END)
            self.vehicle_result.insert(tk.END, result)
            
            self.update_output_tab("Calculate Vehicle Amount", result)
            self.log_calculation("Calculate Vehicle Amount", result)
            self.append_bew_to_file(self.compound_name.get(), bew)
            
        except tk.TclError:
            messagebox.showerror("Input Error", "Please enter valid numeric values.")
    
    def perform_dilution(self):
        try:
            vol_tot_01 = self.dilution_vol_tot_01.get()
            conc_01 = self.dilution_conc_01.get()
            conc_02 = self.dilution_conc_02.get()
            vol_02 = self.dilution_vol_02.get()
            
            conc_ratio = conc_02 / conc_01
            vol_01 = conc_ratio * vol_02
            vol_03 = vol_02 - vol_01
            vol_04 = vol_tot_01 - vol_01
            
            result = f"Dilution Calculation\n"
            result += f"{'='*40}\n"
            result += f"Compound: {self.compound_name.get()}\n"
            result += f"{'='*40}\n"
            result += f"Starting solution concentration: {conc_01:.3g} mg/ml\n"
            result += f"Final solution concentration: {conc_02:.3g} mg/ml\n"
            result += f"Volume of new solution: {vol_02:.3g} ml\n"
            result += f"{'='*40}\n"
            result += f"Mix {vol_01:.3g} ml of your stock solution\n"
            result += f"with {vol_03:.3g} ml of the appropriate vehicle\n"
            result += f"{'='*40}\n"
            result += f"This will leave you with {vol_04:.3g} ml of your stock solution\n"
            result += f"Producing a final volume of {vol_02:.3g} ml\n"
            result += f"{'='*40}\n"
            
            self.dilution_result.delete(1.0, tk.END)
            self.dilution_result.insert(tk.END, result)
            
            self.update_output_tab("Perform Dilution", result)
            self.log_calculation("Perform Dilution", result)
            
        except tk.TclError:
            messagebox.showerror("Input Error", "Please enter valid numeric values.")
    
    def update_output_tab(self, calculation_type, result):
        timestamp = time.strftime('%Y/%m/%d - %H:%M:%S')
        output = f"Date: {timestamp}\n"
        output += f"Calculation Type: {calculation_type}\n"
        output += f"Comments: {self.comments.get('1.0', tk.END).strip()}\n"
        output += result
        output += "\n" + "="*50 + "\n\n"
        
        self.output_text.insert(tk.END, output)
        self.output_text.see(tk.END)  # Scroll to the bottom
    
    def load_bew_values(self):
        try:
            with open("zDrugMakerBEW.txt", 'r') as bew_file:
                bew_values = bew_file.read()
                self.bew_values.delete(1.0, tk.END)
                self.bew_values.insert(tk.END, bew_values)
        except FileNotFoundError:
            self.bew_values.insert(tk.END, "No BEW values found.")
    
    def append_bew_to_file(self, compound_name, bew):
        with open("zDrugMakerBEW.txt", 'a') as bew_file:
            bew_file.write(f"{compound_name} - {bew:.3g}\n")
        self.load_bew_values()
    
    def log_calculation(self, calculation_type, result):
        with open("zDrugMakerLog.txt", 'a') as log_file:
            log_file.write(f"Date: {time.strftime('%Y/%m/%d - %H:%M:%S')}\n")
            log_file.write(f"Calculation Type: {calculation_type}\n")
            log_file.write(result)
            log_file.write("\n" + "="*50 + "\n\n")

if __name__ == "__main__":
    app = ZDrugMakerApp()
    app.mainloop()