from ctypes import WinDLL, create_string_buffer
import os
import time

DLL_PATH = r"C:\Users\Lab Admin\Documents\PythonStuff\pysrs\pysrs\instruments\prior_stage\PriorScientificSDK.dll"
SDKPrior = None
sessionID = None 

def initialize_sdk() -> None:
    '''only useful for send_command(), opens the .dll file to initialize the SDK via WinDLL

    args: none

    returns: non
    '''

    global SDKPrior, sessionID

    if SDKPrior is None:
        if os.path.exists(DLL_PATH):
            SDKPrior = WinDLL(DLL_PATH)
        else:
            raise RuntimeError("DLL could not be loaded.")

        ret = SDKPrior.PriorScientificSDK_Initialise()  
        if ret != 0:
            raise RuntimeError(f"Failed to initialize Prior SDK. Error code: {ret}")

        print("Prior SDK Initialized.")

    if sessionID is None:
        sessionID = SDKPrior.PriorScientificSDK_OpenNewSession()
        if sessionID < 0:
            raise RuntimeError(f"Failed to open Prior SDK session. SessionID: {sessionID}")

        print(f"SDK Session Opened. Session ID: {sessionID}")

def send_command(command: str) -> tuple[int, str]:
    '''main function to send any command to the stage
    
    args: none

    returns: none
    '''

    initialize_sdk()  # error code -10200 heheheheheehruiaewrgilaeuwblaiewjghlkajgbla,knja,ekjb

    rx = create_string_buffer(1000)
    ret = SDKPrior.PriorScientificSDK_cmd(
        sessionID, create_string_buffer(command.encode()), rx
    )
    response = rx.value.decode().strip()

    if ret != 0:
        print(f"Error executing command: {command} (Return Code: {ret})")

    return ret, response

if __name__ == "__main__":
    print("connecting")
    send_command("controller.connect 4")

    send_command(f"controller.z.goto-position 10000") 
    _, current_pos = send_command("controller.z.position.get") 
    print(f"z pos after move: {current_pos}")

    print("disconnectiong")
    send_command("controller.disconnect")
