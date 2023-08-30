import csv
import time
import numpy as np
import pyvisa as visa
from scipy.optimize import curve_fit
from toptica.lasersdk.client import Client, NetworkConnection
from toptica.lasersdk.client import UserLevel, Subscription, Timestamp, SubscriptionValue
from rigol_osc import osc_ask_data
import matplotlib.pyplot as plt
import warnings

# import pandas as pd
# import tkinter as tk
# from tkinter import filedialog
# import matplotlib.pyplot as plt
# import warnings
# import re

def interpolate_voltage_to_wavelength_diff(voltage, fiting_curve_name):
    """Modified from looking up reference table and interpolating to get a polynomial fitting from reference table.
    
    Need a voltage and a fitting curve name, return interpolated_wavelength_diff
    """
    voltage = np.float64(voltage)
    match fiting_curve_name:
        case 'toptica1':
            interpolated_wavelength = 1.41735740e-12 * voltage**5 - 5.70767417e-10 * voltage**4 + 1.15683891e-07 * voltage**3 - 1.37073757e-05 * voltage**2 - 1.58771892e-03 * voltage + 1.55038451e+03 - 1550
            # interpolated_wavelength = 1.41735740e-4 * voltage**5 - 5.70767417e-2 * voltage**4 + 1.15683891e1 * voltage**3 - 1.37073757e3 * voltage**2 - 1.58771892e5 * voltage + 1.55038451e11 - 1550e8
        case 'toptica2':
            interpolated_wavelength = 1.45757887e-12 * voltage**5 - 7.47082544e-10 * voltage**4 + 1.66903897e-07 * voltage**3 - 1.84056335e-05 * voltage**2 - 1.72441280e-03 * voltage + 1.55004321e+03 - 1550
        case _:
            print('[Function]interpolate_voltage_to_wavelength: No such fitting curve name')

    return interpolated_wavelength

DLCPRO_CONNECTION = '192.168.1.28'

"""Get Parameters"""
with Client(NetworkConnection(DLCPRO_CONNECTION)) as client:

    """ read information """
    print(client.get('uptime-txt', str),"===== Connected Device =====")
    print("This is a {} with serial number {}.\nLabel is '{}'".format(
        client.get('system-type'), client.get('serial-number'), client.get('system-label', str)))
    act_wavelength = client.get('laser1:ctl:wavelength-act', float)
    arc_factor = client.get('laser1:dl:pc:external-input:factor', float)
    set_voltage = client.get('laser1:dl:pc:voltage-set', float)

print(f'act_wavelength: {act_wavelength}, arc_factor: {arc_factor}, set_voltage: {set_voltage}')


""" Get Data from Oscilloscope """
data = osc_ask_data([1,2], '1M') # data[0] is time, data[1] is voltage, data[2] is power
time_values = data[0]
voltage_actual_values = data[1] * arc_factor + set_voltage
wavelength_values = interpolate_voltage_to_wavelength_diff(voltage_actual_values, 'toptica1') + act_wavelength
# wavelength_values = interpolate_voltage_to_wavelength_diff(voltage_actual_values, 'toptica1')
power = data[2]


""" Fit the data """
x = time_values
y = power
# Define the math function want to fit
def Lorentz(x,y0,A,xc,w):
    y = y0 + (2*A/np.pi)*(w/(4*(x-xc)**2 + w**2))
    return y

# Define the initial values
y0 = np.average(y[0:1000])

A = 0

min_y_index = np.argmin(y)
min_y = y[min_y_index]
xc = x[min_y_index]

half_y = min_y + (y0-min_y)/2
half_y_index = np.argmin(np.abs(y - half_y))
half_y_x_point = x[half_y_index]
w = np.abs(half_y_x_point - xc)

popt, pcov = curve_fit(Lorentz, x, y, p0=[y0,A,xc,w], maxfev=100000)
# popt, pcov = curve_fit(Lorentz, x, y,  maxfev=10000)
# Evaluate the fitted function over a range of x values
x_fit = np.linspace(x.min(), x.max(), 10000)
y_fit = Lorentz(x_fit, *popt)

# extract the values of a, b, and c from the optimized parameters
y0, A, xc, w = popt

# extract the variances of a, b, and c from the covariance matrix
var_y0, var_A, var_xc, var_w = np.diag(pcov)

# print the results
print(f"y0 = {y0:.8f} +/- {np.sqrt(var_y0):.8f}")
print(f"A = {A:.8f} +/- {np.sqrt(var_A):.8f}")
print(f"xc = {xc:.8f} +/- {np.sqrt(var_xc):.8f}")
print(f"w = {w:.8f} +/- {np.sqrt(var_w):.8f}")

# Plot the original data and the fitted function
plt.plot(x, y, ',', label='Data')
plt.plot(x_fit, y_fit, label='Fitted Function')
# plt.xlim(x.min(), x.max())
plt.legend()
plt.show()


""" Calculate Quality Factor"""
# extract the wavelength at the corresponding time
w0 = wavelength_values[min_y_index]
w = np.abs(wavelength_values[half_y_index] - w0)

q_loaded = w0/2/w
transport0 = min_y/y0

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="invalid value encountered in sqrt")
    q_instinct_under = 2*q_loaded/(1+np.sqrt(transport0))
    q_instinct_over = 2*q_loaded/(1-np.sqrt(transport0))

q_instinct_critical = 2*q_loaded

print(f"FWHM is {2*w}")
print(f"Q_loaded is {q_loaded:.2e}")
print(f"Under couple Q_instinct is {q_instinct_under:.2e}")
print(f"Critical couple Q_instinct is {q_instinct_critical:.2e}")
print(f"Over couple Q_instinct is {q_instinct_over:.2e}")