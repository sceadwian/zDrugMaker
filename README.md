# Leo's Preclinical Pharmacology Companion Scripts

Welcome to Leo's Preclinical Pharmacology Companion Scripts! This collection of Python scripts is designed to assist researchers in various tasks related to preclinical pharmacological studies. From calculating dilutions and volume conversions to allocating subjects into balanced test groups, these scripts aim to streamline your workflow and improve efficiency. Additionally, there are tools for parsing time tracker exports and file analysis.

## Scripts

1. **zDrugMaker_v1_0.py** - Leo's Dilution Calculator and Volume Conversion Applet v1: This is the most recent version of the calculator, capable of handling simple formulations, dilutions, and estimating drug requirements for rodent pharmacological studies. It also features a logging functionality to keep records of your formulations with timestamps.

2. **zAllocator_v1_0.py** - Leo's Group Allocator Script v1: This script facilitates the allocation of subjects into well-balanced test groups based on a single variable. You can input subject IDs and their respective data (e.g., body weight) and specify the final number of groups to be tested. The output is saved in a separate file.

3. **zToggl.py** - Toggl Time Tracker Export Parser: Currently a work in progress, this script aims to parse the detailed Toggl Time Tracker export CSV file and extract hours worked at the lab. It provides a convenient way to analyze your time tracking data. Stay tuned for updates! https://toggl.com/track/

4. **zFarseta_v0_1.py** - zCypher v1: This simple encryption tool transforms legible digital text into an encrypted document that can be decrypted using the same Python script. Version 1 allows for reading sections of the encrypted document at a time.

5. **zFarseta_v0_2.py** - zCypher with Number Hiding Signature v2: Building upon the previous version, this encryption tool includes additional functionality for scrambling numbers, making the encrypted information more challenging to crack. However, please note that small edits to the output may invalidate the entire text, and partial decryption is not possible.

5. **zFarseta_v0_3.py** - zCypher with a GUI v1: Building upon the previous version (version 0_1), this encryption tool does a live encryption/decryption using the same algorith as a bove. It also includes a nice interface.

6. **zFileAnal** - File Analysis Script: Currently a work in progress, this script aims to provide file analysis capabilities. Reports on media files (video and images) contained in the folder.

## Usage

For detailed instructions and usage examples, please refer to the individual script files.
