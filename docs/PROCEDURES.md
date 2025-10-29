# Measurement Procedures

This repository ships a library of PyMeasure `Procedure` classes tailored for the NanoLab laser and transistor test bench. All of them share an instrument manager, configuration-driven parameters, and emit result rows matching their `DATA_COLUMNS`. This document summarises what each procedure does, which instruments it touches, and any special behaviour you should know before modifying or chaining them.

## Foundations
- **BaseProcedure** (`laser_setup/procedures/BaseProcedure.py`)  
  Skeleton for all measurements. It wires common metadata, wraps `startup`/`shutdown` with skip flags, and connects queued instruments through the shared `InstrumentManager`. Override `execute` (and optionally `startup`/`shutdown`) to implement a measurement.
- **ChipProcedure** (`ChipProcedure.py`)  
  Extends `BaseProcedure` with chip-identifying parameters (`chip_group`, `chip_number`, `sample`) and a shutdown hook that can trigger Telegram alerts. Most device procedures inherit from it.
- **Mixins** (`LaserMixin`, `VgMixin`)  
  - `LaserMixin` zeroes laser voltage when `laser_toggle` is off.  
  - `VgMixin` resolves `vg_dynamic` strings (including “DP” placeholders) into numeric gate biases prior to startup.

## Electrical Sweeps
- **IV (I vs Vsd)**  
  Sweeps drain-source voltage using a Keithley 2450 while TENMA supplies bias the gate rails and laser. Emits `[Vsd, I, t, Plate T, Ambient T, Clock]`. Supports repeated sweeps, optional laser burn-in, and temperature logging via a PT100 sensor.
- **IVg (I vs Vg)**  
  Keeps `Vds` fixed and sweeps the gate voltage across a triangular ramp. Optional laser bias and PT100 logging mirror `IV`. Maintains a class-level cache of the last sweep to estimate the Dirac point via resistance peaks.
- **VVg (Vds vs Vg)**  
  Mirrors `IVg` but sources a constant drain current and records the resulting `Vds`. Uses the same gate ramp helper and Dirac-point estimator, making it useful for resistance-focused characterisation.

## Time-Resolved Electrical Traces
- **It (I vs t)**  
  Steps through an ON/OFF/relax laser sequence while biasing `Vds` and `Vg`. Integrates temperature control through a clicker (hotplate controller) once `T_start_t` is reached. Emitted columns include laser voltage and PT100 metrics.
- **It2 (I vs t, 3-phase)**  
  Variant of `It` where the durations of the three phases (laser off/on/off) are individually configurable via `phase1_t`, `phase2_t`, and `phase3_t`. Ideal when you need asymmetric dwell times without editing code.
- **ItVg (I vs t at stepped Vg)**  
  Holds `Vds` constant and steps the gate voltage up/down, recording how the drain current evolves over time at each setpoint. Optional laser burn-in prior to the first step.
- **ItWl (I vs t at stepped wavelength)**  
  Controls the Bentham TLS light source instead of a laser PSU. After a burn-in period with the lamp off, it moves the monochromator to the configured wavelength and records the transient current.
- **Vt (Vds vs t)**  
  Similar to `It`, but the Keithley sources current (`Ids`) and measures the resulting drain voltage. Shares the temperature-control loop with the clicker and laser ON/OFF sequencing.

## Optical Power Measurements
- **LaserCalibration (Power vs VL)**  
  Uses a TENMA PSU to sweep laser drive voltage and a Thorlabs PM100D to average `N_avg` power samples per point. Designed to produce calibration curves for different fibres and wavelengths.
- **Pt (Power vs t)**  
  Logs optical power over time through a three-phase sequence: laser off, laser on, laser off, each lasting proportionally to `laser_T`. Useful for stability and warm-up studies.
- **Pwl (Power vs Wavelength)**  
  Automates a wavelength sweep with the Bentham source while the PM100D records power averages. Each step waits for the monochromator to settle before sampling.

## Thermal Procedures
- **Tt (Temperature vs t)**  
  Commands the clicker to follow a temperature ramp (`T_start`→`T_end`) while the PT100 reader thread streams plate and ambient temperatures. Ideal for verifying thermal profiles independently of electrical bias.

## Utility & Test Procedures
- **FakeProcedure**  
  Generates deterministic-but-variable fake data for UI/testing runs. Emits time vs. pseudo-random values and exposes an estimator list in the GUI.
- **Wait**  
  Busy-waits for `wait_time` seconds, emitting progress updates. Handy for sequence padding.
- **Sequence** (`Sequence.py`)  
  Not a `Procedure`, but a configurably generated container that chains multiple procedures with shared parameter overrides. Parsed from YAML definitions via Hydra resolvers.

## Instrument Summary
Most procedures declare class attributes named after their instrument handles. Common pairings include:
- **Keithley2450** (`meter`): SMU used for sourcing voltage/current and measuring the complementary quantity.
- **TENMA supplies** (`tenma_pos`, `tenma_neg`, `tenma_laser`): Provide gate rails, drain bias, or laser drive voltage, with helper methods for safe ramping and shutdown.
- **PT100SerialSensor** & **Clicker**: Pair of serial instruments for temperature sensing and plate control.
- **ThorlabsPM100USB** (`power_meter`) and **Bentham TLS120Xe** (`light_source`): Optical measurement and wavelength control.

Every instrument is queued through the shared `InstrumentManager`, ensuring connections are deferred until `startup` and released in `shutdown`. If the application runs with `--debug`, these proxies are replaced with `DebugInstrument` so sequences remain executable without hardware.
