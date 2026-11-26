"""
scripts/generate_sbert_dataset.py

Generates domain-specific short-answer training and strictly held-out test datasets
for fine-tuning Sentence Transformers on Python programming concept explanations.
Ensures zero data leakage between train and test splits.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple


def generate_domain_dataset() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ref_path = Path("data/reference_answers.json")
    with open(ref_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    train_pairs: List[Dict[str, Any]] = []
    test_pairs: List[Dict[str, Any]] = []

    # Curated training and held-out test specifications across curriculum concepts
    concept_specs = {
        "Variables": {
            "easy": {
                "train_pos": [
                    "A variable is a symbolic name associated with a value stored in computer memory.",
                    "In Python, a variable serves as a named reference pointing to an object in memory.",
                    "Variables are identifiers that hold data values for reference and manipulation in code."
                ],
                "test_pos": [
                    "A variable acts as a memory reference binding a human-readable name to stored program data.",
                    "Variables allow programmers to label and store information inside system memory for later use."
                ],
                "train_partial": [
                    "A variable stores a number or string in Python.",
                    "Variables are used in code to name things."
                ],
                "test_partial": [
                    "A variable is something you define at the start of a program to hold items."
                ],
                "train_hard_neg": [
                    "A variable is a keyword like if or while that executes operations on numbers.",
                    "The single equals sign in a variable statement tests if two memory locations are equal."
                ],
                "test_hard_neg": [
                    "A variable is a hardware register in the CPU that cannot be modified once set.",
                    "Variable assignment using = compares two expressions and returns True or False."
                ]
            },
            "medium": {
                "train_pos": [
                    "Dynamic typing means variable types are checked at runtime and variables can point to different types.",
                    "In Python, variables are untyped references to typed objects; reassigning rebinds the reference."
                ],
                "test_pos": [
                    "Python resolves types dynamically during runtime; reassigning a variable updates its memory pointer to a new object."
                ],
                "train_partial": [
                    "Python does not require declaring types before using a variable."
                ],
                "test_partial": [
                    "Dynamic typing lets you change variables whenever you want."
                ],
                "train_hard_neg": [
                    "Dynamic typing means variables are statically compiled and cannot change type during program execution.",
                    "Reassigning a variable modifies the underlying data type in-place without changing object memory addresses."
                ],
                "test_hard_neg": [
                    "Python uses static typing where each variable declaration binds a permanent type to that memory address."
                ]
            },
            "hard": {
                "train_pos": [
                    "LEGB defines scope hierarchy: Local, Enclosing, Global, and Built-in namespaces.",
                    "Python resolves variable identifiers following the LEGB lookup sequence from local to built-in."
                ],
                "test_pos": [
                    "Variable lookup in Python searches the Local scope first, then Enclosing functions, Global module, and Built-ins."
                ],
                "train_partial": [
                    "Scope determines whether a variable is local or global in a function."
                ],
                "test_partial": [
                    "LEGB is the rule Python uses to find variables."
                ],
                "train_hard_neg": [
                    "LEGB order means global variables always override local variables inside functions.",
                    "The nonlocal keyword creates a new global variable in the module root."
                ],
                "test_hard_neg": [
                    "Python scope resolution begins at the Built-in scope and cascades down to Local as the last resort."
                ]
            }
        },
        "Conditionals": {
            "easy": {
                "train_pos": [
                    "An if-elif-else construct tests boolean conditions sequentially and runs only the first matching branch.",
                    "Conditional statements direct flow by evaluating expressions and executing the corresponding block."
                ],
                "test_pos": [
                    "If-elif-else statements evaluate conditions in order and execute the block of the first True condition."
                ],
                "train_partial": [
                    "Conditionals check if something is true and run code."
                ],
                "test_partial": [
                    "If statements help the program make decisions based on checks."
                ],
                "train_hard_neg": [
                    "An if-elif-else statement evaluates every condition and executes all branches that evaluate to True.",
                    "The else block runs before any if conditions are evaluated."
                ],
                "test_hard_neg": [
                    "In an if-elif ladder, every branch with a true expression will execute simultaneously."
                ]
            },
            "medium": {
                "train_pos": [
                    "Short-circuit evaluation stops evaluating logical operators as soon as the outcome is determined.",
                    "Python short-circuits 'and' when the first operand is False, and 'or' when the first operand is True."
                ],
                "test_pos": [
                    "Short-circuit evaluation avoids evaluating the second operand if the first operand suffices to determine the boolean result."
                ],
                "train_partial": [
                    "Short circuiting makes boolean logic faster."
                ],
                "test_partial": [
                    "Python skips the rest of the condition when it already knows the answer."
                ],
                "train_hard_neg": [
                    "Short-circuit evaluation guarantees that all operands in a logical expression are always fully computed.",
                    "The 'or' operator evaluates both sides even if the left operand is True."
                ],
                "test_hard_neg": [
                    "Short-circuit evaluation throws an exception whenever a condition contains an error on either side."
                ]
            },
            "hard": {
                "train_pos": [
                    "Truthy and falsy values are non-boolean objects evaluated in a boolean context, where empty containers are false.",
                    "Empty sequences, zero, None, and False are falsy, while non-empty structures evaluate to truthy."
                ],
                "test_pos": [
                    "In Python, objects evaluate as truthy or falsy: zero, empty collections, and None are treated as False in conditions."
                ],
                "train_partial": [
                    "Truthy means true and falsy means false in Python."
                ],
                "test_partial": [
                    "Empty lists and zero count as False in if statements."
                ],
                "train_hard_neg": [
                    "Any non-empty string like 'False' evaluates to falsy in boolean conditionals.",
                    "An empty list [] evaluates to truthy because the list object itself has been allocated."
                ],
                "test_hard_neg": [
                    "In Python, empty lists and dictionaries evaluate to True because they exist in memory."
                ]
            }
        },
        "Loops": {
            "easy": {
                "train_pos": [
                    "A for loop iterates over an iterable, while a while loop repeats as long as a boolean condition remains True.",
                    "For loops traverse collections or ranges; while loops execute continuously until their condition becomes False."
                ],
                "test_pos": [
                    "Use a for loop to iterate through known elements or a sequence, and a while loop when repetition depends on an ongoing condition."
                ],
                "train_partial": [
                    "Loops repeat code multiple times."
                ],
                "test_partial": [
                    "A for loop is for lists and a while loop is for conditions."
                ],
                "train_hard_neg": [
                    "A while loop always executes a predetermined number of times, whereas a for loop never terminates.",
                    "A for loop cannot iterate over sequences or lists in Python."
                ],
                "test_hard_neg": [
                    "A for loop continues indefinitely until a crash occurs, whereas while loops only run once."
                ]
            },
            "medium": {
                "train_pos": [
                    "The break statement exits the loop immediately, whereas continue skips the rest of the current iteration.",
                    "Break terminates loop execution completely; continue advances directly to the next iteration."
                ],
                "test_pos": [
                    "Break terminates the enclosing loop entirely, while continue only skips the remaining statements of the active cycle."
                ],
                "train_partial": [
                    "Break stops things and continue moves on."
                ],
                "test_partial": [
                    "Break exits and continue skips to the next step."
                ],
                "train_hard_neg": [
                    "The continue statement immediately terminates the loop and stops further execution of any future iterations.",
                    "The break statement skips the current element and moves to the next iteration without exiting."
                ],
                "test_hard_neg": [
                    "The continue statement terminates the entire program, whereas break pauses execution for one second."
                ]
            },
            "hard": {
                "train_pos": [
                    "The else clause in a loop executes when the loop completes normally without encountering a break statement.",
                    "A loop else block runs only if the loop terminates via exhaustion of the iterable or condition becoming False, not via break."
                ],
                "test_pos": [
                    "In Python loops, the else block runs upon natural completion of the loop, but is skipped if terminated by a break."
                ],
                "train_partial": [
                    "Loop else executes after the loop finishes."
                ],
                "test_partial": [
                    "The else in a for loop runs at the end."
                ],
                "train_hard_neg": [
                    "A loop else block only executes if the loop was terminated prematurely by a break statement.",
                    "The else block runs before every iteration of the loop body."
                ],
                "test_hard_neg": [
                    "The loop else block is triggered exclusively when an uncaught exception is raised inside the loop."
                ]
            }
        },
        "Functions": {
            "easy": {
                "train_pos": [
                    "A function is a reusable block of code that performs a specific task and optionally returns a value.",
                    "Functions encapsulate modular logic, accept input arguments, and produce outputs via return statements."
                ],
                "test_pos": [
                    "Functions package reusable code blocks to promote modularity, accepting parameters and returning results."
                ],
                "train_partial": [
                    "A function is a piece of code with def."
                ],
                "test_partial": [
                    "Functions let you run the same code multiple times."
                ],
                "train_hard_neg": [
                    "A function in Python cannot return values or take parameters.",
                    "The return statement prints text to the console without sending data back to the caller."
                ],
                "test_hard_neg": [
                    "A function must always contain a print statement; return statements are invalid in Python functions."
                ]
            },
            "medium": {
                "train_pos": [
                    "Parameters are variable names in the function definition, while arguments are the actual values passed during a call.",
                    "A parameter is the placeholder in def f(x), while an argument is the value supplied when calling f(5)."
                ],
                "test_pos": [
                    "Parameters define the input variables expected by a function; arguments are the concrete data values supplied upon invocation."
                ],
                "train_partial": [
                    "Parameters and arguments are inputs to a function."
                ],
                "test_partial": [
                    "One is in the definition and one is in the call."
                ],
                "train_hard_neg": [
                    "Parameters and arguments are identical with no semantic difference; arguments define the function signature.",
                    "Parameters are the values passed during a call, while arguments are the variable names in the definition."
                ],
                "test_hard_neg": [
                    "Parameters are the return values sent to the caller, while arguments are the local variables."
                ]
            },
            "hard": {
                "train_pos": [
                    "A closure is a nested function that retains access to variables from its enclosing lexical scope even after that scope exits.",
                    "Closures capture and remember free variables from the outer enclosing scope."
                ],
                "test_pos": [
                    "A closure occurs when an inner function remembers and accesses bindings from its enclosing function after the outer has returned."
                ],
                "train_partial": [
                    "A closure is a function inside another function."
                ],
                "test_partial": [
                    "Closures have access to outer function variables."
                ],
                "train_hard_neg": [
                    "A closure is a function that automatically closes all open file streams upon returning.",
                    "A closure deletes all local variables as soon as the outer function finishes executing."
                ],
                "test_hard_neg": [
                    "Closures are functions that prevent recursion and force single-threaded execution."
                ]
            }
        },
        "Arrays": {
            "easy": {
                "train_pos": [
                    "Python lists are ordered, mutable sequences that can store heterogeneous data types.",
                    "A list is an indexed collection whose elements can be modified, appended, or removed after creation."
                ],
                "test_pos": [
                    "Lists in Python are dynamic, mutable, ordered collections capable of containing items of various data types."
                ],
                "train_partial": [
                    "A list is a group of items surrounded by square brackets."
                ],
                "test_partial": [
                    "Lists hold multiple values in Python."
                ],
                "train_hard_neg": [
                    "Lists in Python are immutable structures whose size and contents cannot be altered after definition.",
                    "List indexing in Python starts at index 1 and negative indices are syntax errors."
                ],
                "test_hard_neg": [
                    "Python lists are strictly homogeneous and cannot change size or elements once created."
                ]
            },
            "medium": {
                "train_pos": [
                    "Lists are mutable and can be changed in-place, whereas tuples are immutable and fixed once instantiated.",
                    "Tuples cannot be modified after creation, making them hashable and suitable as dictionary keys, unlike lists."
                ],
                "test_pos": [
                    "The fundamental difference is mutability: lists can be modified in-place, while tuples cannot be altered after creation."
                ],
                "train_partial": [
                    "Lists use brackets and tuples use parentheses."
                ],
                "test_partial": [
                    "Tuples cannot change but lists can change."
                ],
                "train_hard_neg": [
                    "Tuples are mutable collections that support append(), whereas lists are strictly immutable.",
                    "Lists can be used as dictionary keys because they are hashable, unlike tuples."
                ],
                "test_hard_neg": [
                    "Tuples can have items added or removed with pop() and append(), whereas lists are locked."
                ]
            },
            "hard": {
                "train_pos": [
                    "A shallow copy duplicates the outer container but shares inner object references; a deep copy recursively duplicates all nested objects.",
                    "Shallow copy leaves nested mutable structures shared, while deepcopy creates completely independent duplicate hierarchies."
                ],
                "test_pos": [
                    "Shallow copy clones the top-level collection while referencing child objects; deep copy recursively copies all nested elements."
                ],
                "train_partial": [
                    "Shallow copies the top level and deep copies everything."
                ],
                "test_partial": [
                    "Deep copy makes a real copy of inner objects."
                ],
                "train_hard_neg": [
                    "A shallow copy completely clones all nested objects so modifications never affect the original.",
                    "Deep copy only copies primitive numbers and ignores nested lists or dictionaries."
                ],
                "test_hard_neg": [
                    "Shallow copy modifies the original list, whereas deep copy deletes the original object from memory."
                ]
            }
        },
        "OOP": {
            "easy": {
                "train_pos": [
                    "A class is a blueprint or template for creating objects, which are concrete instances with state and behavior.",
                    "An object is an instantiated instance of a class, encapsulating data attributes and methods."
                ],
                "test_pos": [
                    "A class acts as a design blueprint defining attributes and methods; an object is an individual instance instantiated from that class."
                ],
                "train_partial": [
                    "Classes have methods and objects are created from them."
                ],
                "test_partial": [
                    "Classes define the structure and objects are the actual items."
                ],
                "train_hard_neg": [
                    "An object is the blueprint that defines a class, and a class is an individual instance in memory.",
                    "Classes in Python cannot contain attributes or methods; only functions can hold state."
                ],
                "test_hard_neg": [
                    "Objects are abstract blueprints used at compile-time, while classes represent running memory instances."
                ]
            },
            "medium": {
                "train_pos": [
                    "The self parameter represents the specific instance of the class being operated upon in a method call.",
                    "Self allows instance methods to access and modify the specific object's attributes and other methods."
                ],
                "test_pos": [
                    "In Python methods, self explicitly references the current instance, allowing access to instance attributes and methods."
                ],
                "train_partial": [
                    "Self refers to the class."
                ],
                "test_partial": [
                    "Self is the first parameter in methods."
                ],
                "train_hard_neg": [
                    "The self parameter references the superclass and prevents the current instance from modifying its own fields.",
                    "Self is a reserved Python keyword that automatically instantiates a new class instance."
                ],
                "test_hard_neg": [
                    "Self refers to the global module scope rather than the instance invoking the method."
                ]
            },
            "hard": {
                "train_pos": [
                    "Polymorphism allows different classes to implement methods with the same name, enabling unified interfaces.",
                    "Polymorphic methods let caller code invoke common operations across disparate object types via duck typing."
                ],
                "test_pos": [
                    "Polymorphism enables objects of different types to respond to the same method invocation in their own specific manner."
                ],
                "train_partial": [
                    "Polymorphism means having many forms in OOP."
                ],
                "test_partial": [
                    "Different classes can have the same method name."
                ],
                "train_hard_neg": [
                    "Polymorphism requires all classes to inherit from the exact same parent class and prohibits method overriding.",
                    "Polymorphism forces all object methods to return None."
                ],
                "test_hard_neg": [
                    "Polymorphism means an object can only belong to one single data type throughout its lifecycle."
                ]
            }
        },
        "Exception Handling": {
            "easy": {
                "train_pos": [
                    "Exception handling catches runtime errors gracefully using try and except blocks to prevent program crashes.",
                    "The try block encloses risky operations, and except catches errors to handle them without terminating execution."
                ],
                "test_pos": [
                    "Try-except blocks intercept runtime exceptions, allowing programs to recover or log errors rather than crashing abruptly."
                ],
                "train_partial": [
                    "Try-except stops your code from crashing on errors."
                ],
                "test_partial": [
                    "You put risky code in try and handle errors in except."
                ],
                "train_hard_neg": [
                    "The except block executes only when the code inside the try block runs successfully without any errors.",
                    "Exception handling catches syntax errors before code execution begins."
                ],
                "test_hard_neg": [
                    "The try block is only executed when an error has already crashed the operating system."
                ]
            },
            "medium": {
                "train_pos": [
                    "The finally block always executes regardless of whether an exception was raised, handled, or absent.",
                    "Finally guarantees execution of cleanup actions like closing files, even if return statements or unhandled errors occur."
                ],
                "test_pos": [
                    "Code in a finally block is guaranteed to execute whether an exception was raised or the try block finished cleanly."
                ],
                "train_partial": [
                    "Finally runs at the very end of exception handling."
                ],
                "test_partial": [
                    "The finally block is used for closing things."
                ],
                "train_hard_neg": [
                    "The finally block only executes if an uncaught exception occurred in the try block.",
                    "The finally block is skipped if the except block successfully handles the error."
                ],
                "test_hard_neg": [
                    "The finally block is skipped whenever a try block finishes without encountering an error."
                ]
            },
            "hard": {
                "train_pos": [
                    "The raise statement manually triggers a built-in or custom exception to signal an exceptional condition.",
                    "Raise propagates an exception object up the call stack to indicate error states."
                ],
                "test_pos": [
                    "Raise explicitly instantiates and triggers an exception, halting normal execution and propagating the error up the stack."
                ],
                "train_partial": [
                    "Raise creates an error on purpose."
                ],
                "test_partial": [
                    "Raise is used to throw an exception in Python."
                ],
                "train_hard_neg": [
                    "The raise statement suppresses all exceptions and forces the function to return True.",
                    "Raise can only be called from inside a catch block in Python."
                ],
                "test_hard_neg": [
                    "The raise keyword automatically repairs corrupted memory and resumes execution."
                ]
            }
        }
    }

    # Helper to construct pairs with canonical reference answer
    for concept, diffs in concept_specs.items():
        for diff, data in diffs.items():
            ref_ans = catalog.get(concept, {}).get("short_answer", {}).get(diff, {}).get("reference_answer", "")
            if not ref_ans:
                continue

            # Train Positives (label 0.90 - 0.95)
            for p in data.get("train_pos", []):
                train_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": p,
                    "reference_answer": ref_ans,
                    "label": 0.92,
                    "category": "positive"
                })

            # Test Positives (label 0.90 - 0.95)
            for p in data.get("test_pos", []):
                test_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": p,
                    "reference_answer": ref_ans,
                    "label": 0.92,
                    "category": "positive"
                })

            # Train Partials (label 0.50)
            for p in data.get("train_partial", []):
                train_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": p,
                    "reference_answer": ref_ans,
                    "label": 0.50,
                    "category": "partial"
                })

            # Test Partials (label 0.50)
            for p in data.get("test_partial", []):
                test_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": p,
                    "reference_answer": ref_ans,
                    "label": 0.50,
                    "category": "partial"
                })

            # Train Hard Negatives (label 0.10)
            for n in data.get("train_hard_neg", []):
                train_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": n,
                    "reference_answer": ref_ans,
                    "label": 0.10,
                    "category": "hard_negative"
                })

            # Test Hard Negatives (label 0.10)
            for n in data.get("test_hard_neg", []):
                test_pairs.append({
                    "concept": concept,
                    "difficulty": diff,
                    "student_text": n,
                    "reference_answer": ref_ans,
                    "label": 0.10,
                    "category": "hard_negative"
                })

    return train_pairs, test_pairs


def main():
    print("Generating domain-specific SBERT training and held-out test datasets...")
    train_pairs, test_pairs = generate_domain_dataset()

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    train_file = data_dir / "sbert_train_dataset.json"
    test_file = data_dir / "sbert_test_dataset.json"

    with open(train_file, "w", encoding="utf-8") as f:
        json.dump(train_pairs, f, indent=2)

    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_pairs, f, indent=2)

    print(f"Generated {len(train_pairs)} training pairs -> {train_file}")
    print(f"Generated {len(test_pairs)} strictly held-out test pairs -> {test_file}")


if __name__ == "__main__":
    from typing import Tuple
    main()
