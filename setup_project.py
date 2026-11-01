import os

def create_project_structure(base_dir="."):
    """
    Creates the standardized 50% Milestone directory structure for 
    Adaptive Knowledge Tracing with Multi-Response Student Behaviour Modeling.
    """
    directories = [
        os.path.join(base_dir, "data", "raw"),
        os.path.join(base_dir, "data", "processed"),
        os.path.join(base_dir, "src"),
        os.path.join(base_dir, "src", "data"),
        os.path.join(base_dir, "src", "models"),
        os.path.join(base_dir, "src", "analyzers"),
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        init_file = os.path.join(directory, "__init__.py")
        # Add __init__.py to python sub-packages
        if "src" in directory and not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Package initialization\n")
        print(f"Created directory: {directory}")

if __name__ == "__main__":
    create_project_structure()
    print("Project directory scaffolding completed successfully.")
