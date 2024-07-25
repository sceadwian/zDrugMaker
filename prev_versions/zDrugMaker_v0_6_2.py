import time

print ("\n================================================================================")
print ("Leo's Dilution Calculator and Volume Conversion Applet v0.6.2\n")
print ("================================================================================")

bew = 1
dose = 0
avgbw = 0
animalnumber = 0
trials = 1
amt = 0
vol01 = 0
now = "time has not been retrieved"

compoundname = input('Name of compound being weighed ')

running = 1
while running:
    now = time.strftime("%Y/%m/%d - %H:%M:%S")
    texta = open("zDrugMakerLog.txt", 'a')
    texta.write('date - %s \n' % (now))
    print ("\n--- Select what you would like to do next: ---\n")
    print ("1. Estimate the amount of drug you need to weight")
    print ("2. Calculate how much vehicle to add to produce your solution")
    print ("3. Dilutions")
    print ("4. Check list of BEW values")
    print ("5. Exit the program")
    print ("6. Version history")
    print ("7. Change drug being weighed")
    print ("8. Print a list of common BEW values\n")

    selection = int(input("Enter your selection: "))

    if selection == 0:
        print ("Please enter a valid number!\n")

    if selection == 1:
        print ("\nPlease enter the following values:\n")
        bew = float(input("BEW of the drug: "))
        dose = float(input("Dose being administered (mg/kg): "))
        avgbw = float(input("average body weight of the animals (g): "))
        animalnumber = int(input("number of animals to be used: "))
        trials = int(input("Number of trials: "))
        print ("\n")

        drugtot = bew * dose * 0.001 * avgbw * animalnumber * trials
        voltot01 = 1 * 0.001 * avgbw * animalnumber * trials
        voltot05 = 5 * 0.001 * avgbw * animalnumber * trials
        voltot10 = 10 * 0.001 * avgbw * animalnumber * trials
#       These calculate the concentration of the solutions at these doses
#        conc01 = drugtot / bew
#        conc05 = drugtot / (bew * 5)
#        conc10 = drugtot / (bew * 10)
        print ("===========================================")
        print ("| Drug amount needed - " , "%.2f" % drugtot , "mg")
        print ("| Rats (1 ml/kg) - " , voltot01 , "ml")
        print ("| Oral (5 ml/kg) - " , voltot05 , "ml")
        print ("| Mice (10 ml/kg) - " , voltot10 , "ml")
        print ("===========================================")
        texta.write("1. Amount of drug needed \n")
        texta.write("Drug name - %s \n BEW - %s \n dose - %s \n Volume total (1 ml/kg) - %s ml \n Volume total (5 ml/kg) - %s ml \n Volume total (10 ml/kg) - %s ml \n\n" % (compoundname, bew, dose, voltot01, voltot05, voltot10))
    
    if selection == 2:
        print ("\nPlease enter the following values:\n")
        bew = float(input("BEW of the drug: "))
        dose = float(input("Dose being administered (mg/kg): "))
        amt = float(input("Amount of drug weighed (mg): "))
        print ("\n")

        voltot01 = amt / (dose * bew)
        voltot05 = (5 * amt) / (dose * bew)
        voltot10 = (10 * amt) / (dose * bew)
# esse lance de %.2f eh pra restringir p/ so 2 decimal places
        print ("================================================================================")
        print ("| Add " , "%.2f" % voltot01 , "ml of vehicle to your " , amt , "mg of drug to produce a 1ml/kg solution")
        print ("| Add " , "%.2f" % voltot05 , "ml of vehicle to your " , amt , "mg of drug to produce a 5ml/kg solution")
        print ("| Add " , "%.2f" % voltot10 , "ml of vehicle to your " , amt , "mg of drug to produce a 10ml/kg solution")
        print ("================================================================================")        
        texta.write("2. Volume of vehicle \n")
        texta.write("Drug name - %s \n BEW - %s \n dose - %s \n amount - %s \n Volume total (1 ml/kg) - %s ml \n Volume total (5 ml/kg) - %s ml \n Volume total (10 ml/kg) - %s ml \n\n" % (compoundname, bew, dose, amt, voltot01, voltot05, voltot10))    

    if selection == 3:
        print ("\nPlease enter the following values:\n")
        voltot01 = float(input("Volume of your starting solution (optional):\n"))
        conc01 = float(input("Concentration of your starting solution:"))
        conc02 = float(input("Concentration of your final solution:"))
        vol02 = float(input("Volume of your new solution:"))
 #      Dilution calculations
 #      voltot01 is the total volume you started with
 #      vol01 is the amount you need of your original solution
 #      vol02 is the amount of your final solutions, V2 as they call it
 #      vol03 is the volume of vehicle you need to add to your vol01
        concRatio = conc02 / conc01
        vol01 = concRatio * vol02  
        vol03 = vol02 - vol01    
        vol04 = voltot01 - vol01
        
        print ("================================================================================")
        print ("| Mix " , vol01 , "ml  of your stock solution " )
        print ("| with " , vol03 , "ml  of the appropriate vehicle " )
        print ("| This will leave you with " , vol04 , "ml  of your stock solution")
        print ("| Producing a final volume of " , vol02 , "ml")
        print ("================================================================================")
        texta.write("3. Dilutions \n")
        texta.write("Drug name - %s \n Original Volume - %sml \n Volume of new solution - %sml \n Stock used - %sml \n Vehicle added - %sml \n\n" % (compoundname, voltot01, vol02, vol01, vol03))    
        selection = 10

    if selection == 4:
        print ("You entered 1\n")      
    if selection == 6:
        print ("Version history")  
        print ("Version 0.0.1\nFirst version of zDrugMaker\n-added menu and menu options\n-added functionality to calculate how much drug to weight out")
        print ("Version 0.0.2\n-added drug maker option to calculate how much vehicle to add based on the amount of drug weight")
        print ("Version 0.0.3\n-compatibility changes for python 3 from python 2.7")
        print ("Version 0.0.4\n-added dilutions functionality\n-polished some of the output text")
        print ("Version 0.0.5\n-added option 6 (dev log)")
        print ("Version 0.0.6\n-added logging capabilities")

    if selection == 7:
        compoundname = input('Name of compound being weighed ')
    
    if selection == 8:
        textr = open("zDrugMakerBEW.txt", 'r')
        print ('\n\n')
        for line in textr:
            print('\t', line, end='')
        textr.close()

    if selection == 10:
        print ("\n\n")
    if selection == 5:
        print ("You entered 5\n\n")
        texta.write('zDrugMaker v.0.0.6\n')
        texta.write('End of session\n\n ------------------------------------------------\n\n')
        texta.close()
        running = 0
    else:
        print ("\n\n\n\n")
