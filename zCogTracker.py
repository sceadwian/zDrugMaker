import random
import time
import csv
from datetime import datetime

def ask_addition_question():
    num1 = random.randint(1000, 9999)
    num2 = random.randint(1000, 9999)
    correct_answer = num1 + num2
    start_time = time.time()
    try:
        user_answer = int(input(f"{num1} + {num2} = "))
        if user_answer == correct_answer:
            print("Correct")
            return time.time() - start_time
        else:
            print(f"Incorrect. The correct answer is {correct_answer}")
            return 60
    except ValueError:
        print(f"Invalid input. The correct answer is {correct_answer}")
        return 60

def ask_simple_multiplication_question():
    num1 = random.randint(1, 9)
    num2 = random.randint(10, 99)
    correct_answer = num1 * num2
    start_time = time.time()
    try:
        user_answer = int(input(f"{num1} * {num2} = "))
        if user_answer == correct_answer:
            print("Correct")
            return time.time() - start_time
        else:
            print(f"Incorrect. The correct answer is {correct_answer}")
            return 60
    except ValueError:
        print(f"Invalid input. The correct answer is {correct_answer}")
        return 60

def ask_subtraction_question():
    num1 = random.randint(100, 999)
    num2 = random.randint(100, 999)
    if num1 < num2:
        num1, num2 = num2, num1
    correct_answer = num1 - num2
    start_time = time.time()
    try:
        user_answer = int(input(f"{num1} - {num2} = "))
        if user_answer == correct_answer:
            print("Correct")
            return time.time() - start_time
        else:
            print(f"Incorrect. The correct answer is {correct_answer}")
            return 60
    except ValueError:
        print(f"Invalid input. The correct answer is {correct_answer}")
        return 60

def cognitive_test():
    mindstate = input("\nPlease comment on your current mindstate: ")

    addition_times = []
    simple_multiplication_times = []
    subtraction_times = []

    print("This application is a cognitive test designed to assess your cognitive ability through a series of math questions. You will be presented with addition, simple multiplication, and subtraction questions. The time you take to answer each question will be recorded. Incorrect answers will be penalized with a time of 60 seconds.")

    print("\nSection 1: Addition Questions")
    start_addition_section = time.time()
    for _ in range(5):
        addition_times.append(ask_addition_question())
    end_addition_section = time.time()

    print("\nSection 2: Simple Multiplication Questions")
    start_simple_multiplication_section = time.time()
    for _ in range(5):
        simple_multiplication_times.append(ask_simple_multiplication_question())
    end_simple_multiplication_section = time.time()

    print("\nSection 3: Subtraction Questions")
    start_subtraction_section = time.time()
    for _ in range(5):
        subtraction_times.append(ask_subtraction_question())
    end_subtraction_section = time.time()

    avg_addition_time = sum(addition_times) / len(addition_times)
    avg_simple_multiplication_time = sum(simple_multiplication_times) / len(simple_multiplication_times)
    avg_subtraction_time = sum(subtraction_times) / len(subtraction_times)

    total_addition_time = end_addition_section - start_addition_section
    total_simple_multiplication_time = end_simple_multiplication_section - start_simple_multiplication_section
    total_subtraction_time = end_subtraction_section - start_subtraction_section

    print("\n--- Test Results ---")
    print(f"Average time for addition questions: {avg_addition_time:.2f} seconds")
    print(f"Average time for simple multiplication questions: {avg_simple_multiplication_time:.2f} seconds")
    print(f"Average time for subtraction questions: {avg_subtraction_time:.2f} seconds")

    now = datetime.now()
    date_time = now.strftime("%Y-%m-%d %H:%M:%S")

    with open("cognitive_test_results.csv", "a", newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["Date and Time", "Avg Addition Time (s)", "Total Addition Time (s)", 
                             "Avg Simple Multiplication Time (s)", "Total Simple Multiplication Time (s)", 
                             "Avg Subtraction Time (s)", "Total Subtraction Time (s)", "Mindstate"])
        writer.writerow([date_time, f"{avg_addition_time:.2f}", f"{total_addition_time:.2f}", 
                         f"{avg_simple_multiplication_time:.2f}", f"{total_simple_multiplication_time:.2f}", 
                         f"{avg_subtraction_time:.2f}", f"{total_subtraction_time:.2f}", mindstate])


    print("\nTest completed and results saved.")
    input("Press Enter to exit the program...")

if __name__ == "__main__":
    cognitive_test()