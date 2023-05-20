import time


def display_intro():
    print("\n" + "=" * 80)
    print("Leo's Dilution Calculator and Volume Conversion Applet v1.0\n")
    print("=" * 80)


def get_compound_name():
    return input('Name of compound being weighed: ')


def log_time(text_file):
    now = time.strftime("%Y/%m/%d - %H:%M:%S")
    text_file.write(f'date - {now} \n')


def display_menu():
    print("\n--- Select what you would like to do next: ---\n")
    print("1. Estimate the amount of drug you need to weight")
    print("2. Calculate how much vehicle to add to produce your solution")
    print("3. Dilutions")
    print("4. Check list of BEW values")
    print("5. Exit the program")
    print("6. Version history")
    print("7. Change drug being weighed")
    print("8. Print a list of common BEW values\n")
    return int(input("Enter your selection: "))


def estimate_drug_amount(compound_name, text_file):
    print("\nPlease enter the following values:\n")
    bew = float(input("BEW of the drug: "))
    append_bew_to_file(compound_name, bew)
    dose = float(input("Dose being administered (mg/kg): "))
    avgbw = float(input("average body weight of the animals (g): "))
    animalnumber = int(input("number of animals to be used: "))
    trials = int(input("Number of trials: "))
    print("\n")

    drugtot = bew * dose * 0.001 * avgbw * animalnumber * trials
    voltot01 = 1 * 0.001 * avgbw * animalnumber * trials
    voltot05 = 5 * 0.001 * avgbw * animalnumber * trials
    voltot10 = 10 * 0.001 * avgbw * animalnumber * trials

    print("============================================")
    print("   Estimated Drug Amount and Volumes")
    print("============================================")
    print(f"  Compound: {compound_name}")
    print(f"  BEW: {bew:.3g} \n  Dose: {dose:.3g} mg/kg")
    print("============================================")
    print(f"  Drug amount needed: {drugtot:.3g} mg")
    print("  Volumes:")
    print(f"  - Rats (1 ml/kg) : {voltot01:.3g} ml")
    print(f"  - Oral (5 ml/kg)  : {voltot05:.3g} ml")
    print(f"  - Mice (10 ml/kg) : {voltot10:.3g} ml")
    print("============================================")
    text_file.write("1. Amount of drug needed \n")
    text_file.write(f"Drug name - {compound_name} \n BEW - {bew:.3g} \n dose - {dose:.3g} \n Volume total (1 ml/kg) - {voltot01:.3g} ml \n Volume total (5 ml/kg) - {voltot05:.3g} ml \n Volume total (10 ml/kg) - {voltot10:.3g} ml \n\n")


def calculate_vehicle_amount(compound_name, text_file):
    print("\nPlease enter the following values:\n")
    bew = float(input("BEW of the drug: "))
    append_bew_to_file(compound_name, bew)
    dose = float(input("Dose being administered (mg/kg): "))
    amt = float(input("Amount of drug weighed (mg): "))
    print("\n")

    vol_tot_01 = amt / (dose * bew)
    vol_tot_05 = (5 * amt) / (dose * bew)
    vol_tot_10 = (10 * amt) / (dose * bew)

    print("==============================================================")
    print("   Vehicle Amounts for Different Concentrations")
    print("==============================================================")
    print(f"  Compound: {compound_name}")
    print(f"  BEW: {bew:.3g} \n  Dose: {dose:.3g} mg/kg")
    print("==============================================================")
    print(f"  Add {vol_tot_01:.3g} ml of vehicle to your {amt:.3g} mg of drug to produce a 1ml/kg solution")
    print(f"  Add {vol_tot_05:.3g} ml of vehicle to your {amt:.3g} mg of drug to produce a 5ml/kg solution")
    print(f"  Add {vol_tot_10:.3g} ml of vehicle to your {amt:.3g} mg of drug to produce a 10ml/kg solution")
    print("==============================================================")

    text_file.write("2. Volume of vehicle \n")
    text_file.write(f"Drug name - {compound_name} \n BEW - {bew:.3g} \n dose - {dose:.3g} \n amount - {amt:.3g} \n Volume total (1 ml/kg) - {vol_tot_01:.3g} ml \n Volume total (5 ml/kg) - {vol_tot_05:.3g} ml \n Volume total (10 ml/kg) - {vol_tot_10:.3g} ml \n\n")


def perform_dilution(compound_name, text_file):
    print("\nPlease enter the following values (in appropriate units):\n")
    vol_tot_01 = float(input("Volume of your starting solution (ml, optional):\n"))
    conc_01 = float(input("Concentration of your starting solution (mg/ml):"))
    conc_02 = float(input("Concentration of your final solution (mg/ml):"))
    vol_02 = float(input("Volume of your new solution (ml):"))

    conc_ratio = conc_02 / conc_01
    vol_01 = conc_ratio * vol_02
    vol_03 = vol_02 - vol_01
    vol_04 = vol_tot_01 - vol_01

    print("==============================================================")
    print("                   Dilution Calculation")
    print("==============================================================")
    print(f"  Compound: {compound_name}")
    print(f"  Starting solution concentration: {conc_01:.3g} mg/ml")
    print(f"  Final solution concentration: {conc_02:.3g} mg/ml")
    print(f"  Volume of new solution: {vol_02:.3g} ml")
    print("==============================================================")
    print(f"  Mix {vol_01:.3g} ml of your stock solution")
    print(f"  with {vol_03:.3g} ml of the appropriate vehicle")
    print(f"  This will leave you with {vol_04:.3g} ml of your stock solution")
    print(f"  Producing a final volume of {vol_02:.3g} ml")
    print("==============================================================")

    text_file.write("3. Dilutions \n")
    text_file.write(f"Drug name - {compound_name} \n Original Volume - {vol_tot_01:.3g}ml \n Volume of new solution - {vol_02:.3g}ml \n Stock used - {vol_01:.3g}ml \n Vehicle added - {vol_03:.3g}ml \n\n")

def check_bew_values():
    print("===========================================")
    print("List of BEW Values:")
    print("===========================================")

    max_line_length = 0
    lines = []

    # Read the file once to find the maximum line length
    with open("zDrugMakerBEW.txt", 'r') as text_file:
        for line in text_file:
            line = line.strip()
            line = line.replace('\t', '    ')  # Replace each tab character with four spaces
            lines.append(line)
            if len(line) > max_line_length:
                max_line_length = len(line)

    # Add 3 to max_line_length to account for extra space and "|"
    max_line_length += 3 

    # Print the top boundary line
    print('=' * max_line_length)

    # Read the file again to print the lines, padding each one to the maximum length
    for line in lines:
        print(f"| {line:<{max_line_length - 2}}|")

    # Print the bottom boundary line
    print('=' * max_line_length)



def display_version_history():
    print("Version history")
    print("Version 0.0.1\nFirst version of zDrugMaker\n-added menu and menu options\n-added functionality to calculate how much drug to weight out")
    print("Version 0.0.2\n-added drug maker option to calculate how much vehicle to add based on the amount of drug weight")
    print("Version 0.0.3\n-compatibility changes for python 3 from python 2.7")
    print("Version 0.0.4\n-added dilutions functionality\n-polished some of the output text")
    print("Version 0.0.5\n-added option 6 (dev log)")
    print("Version 0.0.6\n-added logging capabilities")
    print("Version 1.0\n-updated an streamlined code\n-added more logging capabilities (BEW logger)")

def print_common_bew_values():
    with open("zDrugMakerBEW.txt", 'r') as text_file:
        print('\n\n')
        for line in text_file:
            print('\t', line, end='')

def append_bew_to_file(compound_name, bew):
    with open("zDrugMakerBEW.txt", 'a') as bew_file:
        bew_file.write(f"{compound_name} - {bew:.3g}\n")



# ... Rest of the functions

def main():
    display_intro()
    compound_name = get_compound_name()
    running = True
    with open("zDrugMakerLog.txt", 'a') as text_file:
        while running:
            log_time(text_file)
            selection = display_menu()

            if selection == 1:
                estimate_drug_amount(compound_name, text_file)
            elif selection == 2:
                calculate_vehicle_amount(compound_name, text_file)
            elif selection == 3:
                perform_dilution(compound_name, text_file)
            elif selection == 4:
                check_bew_values()
            elif selection == 6:
                display_version_history()
            elif selection == 7:
                compound_name = input('Name of compound being weighed: ')
            elif selection == 8:
                print_common_bew_values()
            elif selection == 9:
                ##functon to sort through the BEW file and remove duplicates and sort in alphabetical order (maybe) backup file with date timestamp before applying this feature.
                with open("zDrugMakerBEW.txt", 'r') as text_file:
                    #unfinished
            elif selection == 5:
                running = False
                text_file.write('zDrugMaker v.1.0\n')
                text_file.write('End of session\n\n ------------------------------------------------\n\n')
                print("Goodbye!")
            else:
                print("Please enter a valid number!\n")



if __name__ == "__main__":
    main()



