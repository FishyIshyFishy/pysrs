import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time
from pysrs.aaaa.instruments.galvos import Galvo
from pysrs.aaaa.gui.gui import GUI
import threading, time, os
from PIL import Image
from tkinter import messagebox
from pysrs.mains.utils import generate_data

class Acquisition:
    def __init__(self, ai_chans: list[str], ao_chans: list[str], galvo: Galvo, gui: GUI, config: dict = {}, **kwargs):
        '''create an acquisition coordinating object
        
        args:
            ao_chans: array of 2 output channel names for galvo mirrors, e.g. ao1, ao0
            ai_chans: array of N input channel names for data reading chans, e.g. ai1, ai2, ai3
            galvo: galvo mirrors object to hold how to scan
            gui: main GUI for getting what type of scan to do
        
        returns: none
        '''

        self.ai_chans = ai_chans
        self.ao_chans = ao_chans
        self.galvo = galvo
        self.gui = gui

        if isinstance(self.ai_chans, str):
            self.ai_chans = [self.ai_chans]  # ai chans is annoyingly only a string if 1 channel, but its easier to just wrap it here    

    def start_scan(self): 
        '''prepare to thread the scanning process

        args:
            gui: main gui to get what type of acquisition should be done

        returns: none
        '''

        if self.gui.running:
            messagebox.showwarning('Warning', 'Scan is already running.')

        if self.gui.rpoc_enabled.get() and self.gui.apply_mask_var.get():
            def do_the_thing():
                return 0
            do_the_thing()
        
        self.gui.running = True
        self.gui.continuous_button['state'] = 'disabled'
        self.gui.stop_button['state'] = 'normal'

        threading.Thread(target=self.scan, daemon=True).start()

    def scan(self):
        '''function that basically chooses whether to simulate or actually acquire
        
        args: none
        
        returns: none
        '''

        try: 
            while self.gui.running:
                self.gui.update_config()

                channels = []
                for chan in self.gui.config['device']:
                    channels.append(f'{self.gui.config['device']}/{chan}')
                
                if self.gui.simulation_mode.get():
                    self.gui.data = generate_data(len(channels), config=self.gui.config)
                else: 
                    self.gui.data = self.acquire_single()
                self.gui.root.after(0, self.gui.display_data)
        except Exception as e:
            messagebox.showerror('Data Acquisition Error', f'Cannot display data: {e}')
        finally:
            self.gui.running = False
            self.gui.continuous_button['state'] = 'normal'  
            self.gui.stop_button['state'] = 'disabled'

    def stop_scan(self):
        '''reset the acquisition to the off state for all parameters

        args: none
        
        returns: none
        '''

        self.gui.running = False
        self.gui.acquiring = False
        self.gui.continuous_button['state'] = 'normal'
        self.gui.stop_button['state'] = 'disabled'
        self.gui.single_button['state'] = 'normal'
                

    def acquire_single(self):
        '''acquire a single acquistion with 2 AOs (galvos) and variable AIs (PMTs, lockin, etc.)

        args: none

        returns: data array, arr[i] is the i+1th channel's cropped 2D data
        '''

        if isinstance(self.ai_chans, str): 
            self.ai_chans = [self.ai_chans] # probably unecessary
        
        with nidaqmx.Task() as ao_task, nidaqmx.Task() as ai_task:
            for chan in self.galvo.ao_chans:
                ao_task.ao_channels.add_ao_voltage_chan(f'{self.galvo.device}/{chan}')
            ao_task.timing.cfg_samp_clk_timing(
                rate=self.galvo.rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self.galvo.total_samples
            )

            for chan in self.ai_chans:
                ai_task.ai_channels.add_ai_voltage_chan(f'{self.galvo.device}/{chan}')
            ai_task.timing.cfg_samp_clk_timing(
                rate=self.galvo.rate,
                source=f'/{self.galvo.device}/ao/SampleClock', # set the input task to read off the same clock as the galvos
                sample_mode=AcquisitionType.FINITE,
                amps_per_chan=self.galvo.total_samples
            )

            ao_task.write(self.galvo.waveform, auto_start=False)
            ai_task.start() # start this first, because it uses the ao task to begin so its ok to wait
            ao_task.start()

            ao_task.wait_until_done(timeout=self.galvo.total_samples / self.galvo.rate + 5) 
            ai_task.wait_until_done(timeout=self.galvo.total_samples / self.galvo.rate + 5) # order of waiting shouldnt matter since they use the same clock

            data = np.array(ai_task.read(number_of_samples_per_channel=self.galvo.total_samples)) # thanks for the nice variable name nidaqmx devs

        numchans = len(self.ai_chans)
        output = []

        if numchans == 1:
            data = data.reshape(self.galvo.total_y, self.galvo.total_x, self.galvo.pixel_samples)
            data = np.mean(data, axis=2)
            output = data[:,self.galvo.extrasteps_left:-self.galvo.extrasteps_right]
            return [output] # surely i dont have to rewrap this array 
        else:
            for i in range(numchans):
                chan_data = data[i]  # shape=(total_samples,)
                chan_data = chan_data.reshape(self.galvo.total_y, self.galvo.total_x, self.galvo.pixel_samples)
                data2d = np.mean(chan_data, axis=2)
                cropped = data2d[:,self.galvo.extrasteps_left:-self.galvo.extrasteps_right]
                output.append(cropped)
            return output


    def acquire_single_rpoc(self):
        return 0