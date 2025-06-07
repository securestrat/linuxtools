import subprocess
def get_cpu_info():
    """
    Determine the number of CPU sockets and cores per socket using the `lscpu` command.

    Returns:
        dict or None: A dictionary with 'sockets' and 'cores_per_socket' if successful, None if an error occurs.
    """
    try:
        # Run the 'lscpu' command and capture its output
        output = subprocess.check_output(
            ['lscpu'],
            stderr=subprocess.STDOUT,
            text=True
        )

        sockets = None
        cores_per_socket = None

        # Parse the output for relevant lines
        for line in output.splitlines():
            if line.startswith('Socket(s):'):
                sockets = int(line.split(':')[1].strip())
            elif line.startswith('Core(s) per socket:'):
                cores_per_socket = int(line.split(':')[1].strip())

        # Check if both values were found
        if sockets is None or cores_per_socket is None:
            print("Missing required information in lscpu output.")
            return None

        return {'sockets': sockets, 'cores_per_socket': cores_per_socket}

    except subprocess.CalledProcessError as e:
        print(f"Error running 'lscpu': {e}")
        return None
    except FileNotFoundError:
        print("The 'lscpu' command is not available. Please install it.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# Module level variables (if needed)
__version__ = '1.0.0'
__all__ = ['get_cpu_info']

# Optional: provide a convenient way to run the module directly
if __name__ == "__main__":
    cpu_info = get_cpu_info()
    if cpu_info is not None:
        print(f"Number of CPU sockets: {cpu_info['sockets']}")
        print(f"Number of cores per socket: {cpu_info['cores_per_socket']}")
else:
    print("Failed to determine CPU information.")



