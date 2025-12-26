# Copyright (c) 2019 Esben Rossel
# All rights reserved.
#
# Author: Esben Rossel <esbenrossel@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.


from tkinter import messagebox
import serial
import numpy as np

from spectrometer import config
import threading
import tkinter as ttk
import time


# The firmware expects 12 bytes from the computer and will not do anything until 12 bytes have been received.
# The format is:
# byte[1-2]: The characters E and R. Defines where the firmware should start reading in its circular input-buffer.
# byte[3-6]: The 4 bytes constituting the 32-bit int holding the SH-period
# byte[7-10]: The 4 bytes constituting the 32-bit int holding the ICG-period
# byte[11]: Continuous flag: 0 equals one acquisition, 1 equals continuous mode
# byte[12]: The number of integrations to average
def rxtx(panel, SerQueue, progress_var):
    threadser = None
    if config.AVGn[0] == 0:
        threadser = threading.Thread(
            target=rxtxoncethread, args=(panel, SerQueue, progress_var), daemon=True
        )
    elif config.AVGn[0] == 1:
        threadser = threading.Thread(
            target=rxtxcontthread, args=(panel, progress_var), daemon=True
        )
    if threadser is not None:
        threadser.start()


def rxtxoncethread(panel, SerQueue, progress_var):
    # open serial port
    try:
        ser = serial.Serial(config.port, config.baudrate)
        # share the serial handle with the stop-thread so cancel_read may be called
        SerQueue.put(ser)
        # disable controls
        panelsleep(panel)
        config.stopsignal = 0

        # start the progressbar
        panel.progress.config(mode="determinate")
        threadprogress = threading.Thread(
            target=progressthread, args=(progress_var,), daemon=True
        )
        threadprogress.start()

        # wait to clear the input and output buffers, if they're not empty data is corrupted
        while ser.in_waiting > 0:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.01)

        # Determine hardware vs software averaging
        # Firmware supports max 15 averages, so for >15 we need software averaging
        requested_avg = config.AVGn[1]
        if requested_avg <= 15:
            # Use hardware averaging only
            hardware_avg = requested_avg
            software_iterations = 1
        else:
            # Use max hardware averaging (15) and do multiple collections in software
            hardware_avg = 15
            software_iterations = int(np.ceil(requested_avg / 15.0))

        # Accumulator for software averaging (use float32 to avoid overflow)
        if software_iterations > 1:
            accumulated_data = np.zeros(3694, dtype=np.float32)

        # Transmit key 'ER'
        config.txfull[0] = 69
        config.txfull[1] = 82
        # split 32-bit integers to be sent into 8-bit data
        config.txfull[2] = (config.SHperiod >> 24) & 0xFF
        config.txfull[3] = (config.SHperiod >> 16) & 0xFF
        config.txfull[4] = (config.SHperiod >> 8) & 0xFF
        config.txfull[5] = config.SHperiod & 0xFF
        config.txfull[6] = (config.ICGperiod >> 24) & 0xFF
        config.txfull[7] = (config.ICGperiod >> 16) & 0xFF
        config.txfull[8] = (config.ICGperiod >> 8) & 0xFF
        config.txfull[9] = config.ICGperiod & 0xFF
        # averages to perfom (send hardware average count)
        config.txfull[10] = config.AVGn[0]
        config.txfull[11] = hardware_avg

        # Perform software averaging by collecting multiple times
        for iteration in range(software_iterations):
            if config.stopsignal != 0:
                break

            # transmit everything at once (the USB-firmware does not work if all bytes are not transmitted in one go)
            ser.write(config.txfull)

            # wait for the firmware to return data
            config.rxData8 = ser.read(7388)

            # combine received bytes into 16-bit data
            for rxi in range(3694):
                value = (config.rxData8[2 * rxi + 1] << 8) + config.rxData8[2 * rxi]
                if software_iterations > 1:
                    accumulated_data[rxi] += value
                else:
                    config.rxData16[rxi] = value

        # close serial port
        ser.close()

        # enable all buttons
        panelwakeup(panel)

        if config.stopsignal == 0:
            # If we did software averaging, compute the average
            if software_iterations > 1:
                for rxi in range(3694):
                    config.rxData16[rxi] = np.uint16(np.round(accumulated_data[rxi] / software_iterations))

            # plot the new data
            panel.bupdate.invoke()
            # hold values for saving data to file as the SHperiod and ICGperiod may be updated after acquisition
            config.SHsent = config.SHperiod
            config.ICGsent = config.ICGperiod

        SerQueue.queue.clear()

    except serial.SerialException:
        messagebox.showerror(
            "pySPEC",
            "There's a problem with the specified serial connection.",
        )


def rxtxcontthread(panel, progress_var):
    # open serial port
    try:
        ser = serial.Serial(config.port, config.baudrate)
        # disable controls
        panelsleep(panel)
        config.stopsignal = 0

        # restart the progressbar for each acquisition
        panel.progress.config(mode="indeterminate")
        panel.progress.start(100)
        #        threadprogress = threading.Thread(target=progressthread, args=(progress_var), daemon=True)
        #        threadprogress.start()

        # wait to clear the input and output buffers, if they're not empty data is corrupted
        while ser.in_waiting > 0:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)

        # Transmit key 'ER'
        config.txfull[0] = 69
        config.txfull[1] = 82
        # split 32-bit integers to be sent into 8-bit data
        config.txfull[2] = (config.SHperiod >> 24) & 0xFF
        config.txfull[3] = (config.SHperiod >> 16) & 0xFF
        config.txfull[4] = (config.SHperiod >> 8) & 0xFF
        config.txfull[5] = config.SHperiod & 0xFF
        config.txfull[6] = (config.ICGperiod >> 24) & 0xFF
        config.txfull[7] = (config.ICGperiod >> 16) & 0xFF
        config.txfull[8] = (config.ICGperiod >> 8) & 0xFF
        config.txfull[9] = config.ICGperiod & 0xFF
        # averages to perfom
        config.txfull[10] = config.AVGn[0]
        config.txfull[11] = config.AVGn[1]

        # transmit everything at once (the USB-firmware does not work if all bytes are not transmittet in one go)
        ser.write(config.txfull)

        # loop to acquire and plot data continuously
        while config.stopsignal == 0:
            # wait for the firmware to return data
            config.rxData8 = ser.read(7388)

            if config.stopsignal == 0:
                # combine received bytes into 16-bit data
                for rxi in range(3694):
                    config.rxData16[rxi] = (
                        config.rxData8[2 * rxi + 1] << 8
                    ) + config.rxData8[2 * rxi]

                # plot the new data
                panel.bupdate.invoke()
                # hold values for saving data to file
                config.SHsent = config.SHperiod
                config.ICGsent = config.ICGperiod

        # resend settings with continuous transmission disabled to avoid flooding of the serial port
        config.txfull[10] = 0
        ser.write(config.txfull)

        # wait until data is received to close the serial port
        while ser.out_waiting > 0:
            time.sleep(0.1)

        # close serial port
        ser.close()
        panelwakeup(panel)
        panel.progress.stop()

    except serial.SerialException:
        messagebox.showerror(
            "pySPEC",
            "There's a problem with the specified serial connection.",
        )


def progressthread(progress_var):
    progress_var.set(0)
    
    # Calculate total time considering software averaging
    requested_avg = config.AVGn[1]
    if requested_avg <= 15:
        # Hardware averaging only
        hardware_avg = requested_avg
        software_iterations = 1
    else:
        # Software averaging with multiple collections
        hardware_avg = 15
        software_iterations = int(np.ceil(requested_avg / 15.0))
    
    # Total time is: ICGperiod * hardware_avg * software_iterations
    total_time = config.ICGperiod * hardware_avg * software_iterations / config.MCLK
    
    for i in range(1, 11):
        progress_var.set(i)
        # wait 1/10th of the total acquisition time before adding to progress bar
        time.sleep(total_time / 10)


def rxtxcancel(SerQueue):
    config.stopsignal = 1
    # Are we stopping one very long measurement, or the continuous real-time view?
    if config.AVGn[0] == 0:
        ser = SerQueue.get()
        ser.cancel_read()


def panelsleep(panel):
    panel.bstop.config(state=ttk.NORMAL)
    panel.bopen.config(state=ttk.DISABLED)
    panel.bsave.config(state=ttk.DISABLED)
    panel.bcollect.config(state=ttk.DISABLED)
    panel.AVGscale.config(state=ttk.DISABLED)
    panel.rcontinuous.config(state=ttk.DISABLED)
    panel.roneshot.config(state=ttk.DISABLED)
    panel.eICG.config(state=ttk.DISABLED)
    panel.eSH.config(state=ttk.DISABLED)
    panel.edevice.config(state=ttk.DISABLED)
    panel.cinvert.config(state=ttk.DISABLED)
    panel.cbalance.config(state=ttk.DISABLED)
    try:
        panel.cmirror.config(state=ttk.DISABLED)
    except Exception:
        pass


def panelwakeup(panel):
    panel.bstop.config(state=ttk.DISABLED)
    panel.bopen.config(state=ttk.NORMAL)
    panel.bsave.config(state=ttk.NORMAL)
    panel.bcollect.config(state=ttk.NORMAL)
    panel.AVGscale.config(state=ttk.NORMAL)
    panel.rcontinuous.config(state=ttk.NORMAL)
    panel.roneshot.config(state=ttk.NORMAL)
    panel.eICG.config(state=ttk.NORMAL)
    panel.eSH.config(state=ttk.NORMAL)
    panel.edevice.config(state=ttk.NORMAL)
    panel.cinvert.config(state=ttk.NORMAL)
    try:
        panel.cmirror.config(state=ttk.NORMAL)
    except Exception:
        pass
    if config.datainvert == 1:
        panel.cbalance.config(state=ttk.NORMAL)
