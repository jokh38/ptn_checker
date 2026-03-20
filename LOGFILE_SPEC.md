
# 1. Purpose

This document describes the contents of the scanning result file generated during scanning irradiation and explains how to convert the recorded data into physical values.

* The database and files on TCSC required for conversion are essential for system operation.
* Before referencing these files, notification is required and modification is prohibited.
* The system provider assumes no responsibility for issues caused by external access.

**Reference file:**

* `FileNameSPDefinition.txt`

  * Location: `TCSC_PC / D:\TCSC_DATA\Work\makeMP`

---

# 2. Details

## 2.1 Scan performance data details

* Scan result files are stored in **binary format**.
* Each row consists of **8 data elements (Bank1 ~ Bank8)**.
* Each element is a **16-bit integer**.
* Time interval between rows: **15 μs**

### Data structure (per row)

| Bank  | Content                       |
| ----- | ----------------------------- |
| Bank1 | Beam position actual (X)      |
| Bank2 | Beam position actual (Y)      |
| Bank3 | Beam size (X)                 |
| Bank4 | Beam size (Y)                 |
| Bank5 | Dose1 actual (beam intensity) |
| Bank6 | Dose2 actual (beam intensity) |
| Bank7 | Layer number (0–7 bit used)   |
| Bank8 | Scan number & Beam On/Off     |

### Bank8 bit structure

* 15 bit: Beam On/Off (Plan)
* 14 bit: Beam On/Off (Actual)
* 13–7 bit: Not used
* 6–0 bit: Scan number

### Notes

* All data is stored in binary.
* All banks are in **big endian format**.

---

## 2.2 Conversion to physical values

Conversion formulas are provided for:

* Beam position (X, Y)
* Beam intensity (Dose1, Dose2)

Conversion constants depend on nozzle type.

---

## 2.2.1 Beam position

### General formula

```
Beam position (mm) = (measured value - center of measurement) × conversion factor
```

* Measured value: binary data
* Measurement center:

  * X = 16383 (MPN)
  * Y = 16383 (MPN)

---

### 2.2.1.1 Multi-purpose nozzle (MPN)

#### Conversion factor (Isocenter)

```
IC(X) = {(RefCH1+ − RefCH1−) × SAD / (SAD − ElectrodeDistance)} / 32767
IC(Y) = {(RefCH2+ − RefCH2−) × SAD / (SAD − ElectrodeDistance)} / 32767
```

---

### 2.2.1.2 Dedicated scanning nozzle (DSN)

#### Measurement center

* X = 24575
* Y = 32767

#### Conversion factor (Isocenter)

```
IC(X) = {(RefCH1+ − RefCH1−) × SAD / (SAD − ElectrodeDistance)} / 49151
IC(Y) = {(RefCH2+ − RefCH2−) × SAD / (SAD − ElectrodeDistance)} / 65535
```

#### Conversion factor (Monitor position)

```
M(X) = (RefCH1+ − RefCH1−) / 49151
M(Y) = (RefCH2+ − RefCH2−) / 65535
```

---

## 2.2.2 Beam intensity

### Basic formula

```
Intensity (MUraw/s) = Monitor Full Range × (measured value / 65535) × factor
```

### Monitor Full Range (by DOSE1_RANGE)

| DOSE1_RANGE | Full Range |
| ----------- | ---------- |
| 1           | 160 nA     |
| 2           | 470 nA     |
| 3           | 1400 nA    |
| 4           | 4200 nA    |
| 5           | 12600 nA   |

* Stored in:

  * `RT_RECORD_LAYER` (column 21)
  * `PATIENT_QA_SCAN_RES` (column 29 or 35)

---

### Factor definition

```
factor = 1 / DM_CALC_FACTOR_B
```

* Stored in database: `DM_CALC_FACTOR`

---

### Standard condition conversion

```
Intensity (MU/s) = Intensity (MUraw/s) × K × kTP
```

#### Dose rate correction factor (K)

* Depends on beam energy and dose rate
* Stored in database: `COEFF_CRAW_E`
* If missing → use 2D interpolation (future: 3D interpolation)

---

#### Temperature & pressure correction (kTP)

```
kTP = (273.2 + T) / (273.2 + T0) × (P0 / P)
```

* T0 = 22.0°C
* P0 = 101.33 kPa
* T, P from measurement environment

---

## 2.3 Others

### 2.3.1 Result file

* Storage path:

```
D:\TCSC_DATA\patient\<patientID>\<planID>\Actual\Scanning\
```

* Naming convention:

```
<RoomNo>_<PatientID>_<PlanID>_<FieldNo>_<LayerNo>.ptn
```

* Example:

```
01-0123456_037_002_001.ptn
```

* File name reference:

  * `RT_RECORD_LAYER` column 24 (`SCAN_OUT_FL_NM`)

---

### 2.3.2 Others

* If irradiation is interrupted (interlock):

  * After restart, scanning resumes from the first spot of that layer.
  * Beam is temporarily turned off (idle shot), then restarted.
  * Both pre-stop and post-restart data are recorded.
  * Idle firing data is also included.

### Beam On/Off (Actual) interpretation

* 1 = On
* 0 = Off

### Bit structure (Bank8)

| Bit  | Meaning              |
| ---- | -------------------- |
| 15   | Beam On/Off (Plan)   |
| 14   | Beam On/Off (Actual) |
| 13–7 | Not used             |
| 6–0  | Rescanning number    |

#### Example

* Rescanning number = 1 → `0000001`
* Rescanning number = 2 → `0000010`
