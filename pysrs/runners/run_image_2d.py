import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time
from pysrs.instruments.galvo_funcs import Galvo

@staticmethod
def lockin_scan(lockin_chan, galvo):
    """
    Now supports either:
      - lockin_chan: str (single channel, e.g. 'Dev1/ai0')
      - lockin_chan: list of strings (multiple channels, e.g. ['Dev1/ai0','Dev1/ai1'])
    Returns: 2D or list of 2D, depending on how many channels.
    """
    # --------------------------------------------------------
    # 1) Convert lockin_chan to a list, if it's a single string
    # --------------------------------------------------------
    if isinstance(lockin_chan, str):
        lockin_chan = [lockin_chan]  # wrap single in list

    # --------------------------------------------------------
    # 2) Create tasks
    # --------------------------------------------------------
    with nidaqmx.Task() as ao_task, nidaqmx.Task() as ai_task:
        # Add the two AO channels for the galvos
        ao_task.ao_channels.add_ao_voltage_chan(f'{galvo.device}/{galvo.ao_chans[0]}')
        ao_task.ao_channels.add_ao_voltage_chan(f'{galvo.device}/{galvo.ao_chans[1]}')

        # For each lock-in channel, add an AI channel
        for ch in lockin_chan:
            ai_task.ai_channels.add_ai_voltage_chan(ch)

        ao_task.timing.cfg_samp_clk_timing(
            rate=galvo.rate,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=galvo.total_samples
        )
        ai_task.timing.cfg_samp_clk_timing(
            rate=galvo.rate,
            source=f'/{galvo.device}/ao/SampleClock',
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=galvo.total_samples
        )

        # Start tasks
        ao_task.write(galvo.waveform, auto_start=False)
        ai_task.start()
        ao_task.start()

        ao_task.wait_until_done(timeout=galvo.total_samples / galvo.rate + 5)
        ai_task.wait_until_done(timeout=galvo.total_samples / galvo.rate + 5)

        # ai_task.read() returns a list-of-lists if there are multiple AI channels
        lockin_data = np.array(
            ai_task.read(
                number_of_samples_per_channel=galvo.total_samples
            )
        )
        # lockin_data shape -> (nChan, total_samples)

    # --------------------------------------------------------
    # 3) Reshape each channel's data -> (total_y, total_x, pixel_samples), then average
    # --------------------------------------------------------
    # If there's only 1 channel, lockin_data is shape (total_samples,).
    # If multiple channels, shape (nChan, total_samples).
    nChan = len(lockin_chan)
    out_list = []

    if nChan == 1:
        lockin_data = lockin_data.reshape(galvo.total_y, galvo.total_x, galvo.pixel_samples)
        data = np.mean(lockin_data, axis=2)
        cropped = data[galvo.numsteps_extra:-galvo.numsteps_extra, galvo.numsteps_extra:-galvo.numsteps_extra]
        return cropped
    else:
        # multiple channels
        for i in range(nChan):
            chan_data = lockin_data[i]  # shape=(total_samples,)
            chan_data = chan_data.reshape(galvo.total_y, galvo.total_x, galvo.pixel_samples)
            data2d = np.mean(chan_data, axis=2)
            cropped = data2d[galvo.numsteps_extra:-galvo.numsteps_extra,
                             galvo.numsteps_extra:-galvo.numsteps_extra]
            out_list.append(cropped)
        return out_list

def plot_image(data: np.ndarray, galvo: Galvo, savedat=True) -> None:
    if savedat:
        np.savez('scanned_data.npz', data=data, **galvo.__dict__)

    plt.imshow(data, 
               extent=[-galvo.amp_x, galvo.amp_x, -galvo.amp_y, galvo.amp_y], 
               origin='lower', 
               aspect='auto', 
               cmap='gray')
    plt.colorbar(label="Lock-in amplitude (V)")
    plt.title("Raster Scanned Image with Lock-in Data")
    plt.xlabel('Galvo X Voltage')
    plt.ylabel('Galvo Y Voltage')
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'],  # Galvo connections
        "amp_x": 0.5,
        "amp_y": 0.5,
        "rate": 1e5,  # Hz
        "numsteps_x": 400,
        "numsteps_y": 400,
        "dwell": 10,  # us
        "numsteps_extra": 100
    }
    galvo = Galvo(config)

    data = lockin_scan('Dev1/ai0', galvo)
    plot_image(data, galvo)