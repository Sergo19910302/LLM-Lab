\## MTBF, MTTF and MTTR

MTBF (Mean Time Between Failures) is the average operating time between failures of a repairable system.

MTTF (Mean Time To Failure) is used for non-repairable items. MTTR (Mean Time To Repair) is the average time

needed to restore a system after a failure.



\## Availability

Inherent availability is calculated as MTBF / (MTBF + MTTR). It is the share of time a repairable system is

able to operate. Availability improves when MTBF grows or when MTTR becomes shorter.



\## Weibull distribution

The Weibull distribution is the most commonly used distribution for life data analysis in reliability engineering.

Its shape parameter beta describes the failure pattern: beta < 1 means a decreasing failure rate (early failures),

beta = 1 means a constant failure rate (random failures), beta > 1 means an increasing failure rate (wear-out).



\## Exponential distribution

When the failure rate is constant over time, the time to failure follows the exponential distribution.

It is a special case of the Weibull distribution with beta = 1. For it, MTBF = 1 / failure rate.



\## Bathtub curve

The bathtub curve has three phases. First, early failures (infant mortality) with a decreasing failure rate.

Second, the useful life phase with random failures and a roughly constant rate. Third, the wear-out phase

with an increasing failure rate.

In plain words: as equipment gets old and worn, it starts to fail more often (aging, wear-out).



\## HALT and HASS

HALT (Highly Accelerated Life Test) applies stresses far beyond specifications, such as temperature steps and

vibration, to find design weaknesses quickly. HASS (Highly Accelerated Stress Screen) is used in production

to screen out units with manufacturing defects.



\## Arrhenius model

The Arrhenius model describes how temperature accelerates chemical failure mechanisms. It is used to calculate

the acceleration factor between a high test temperature and normal use temperature.



\## FMEA

FMEA (Failure Mode and Effects Analysis) is a structured method to find possible failure modes, their effects

and causes. Risks are ranked, for example with severity, occurrence and detection ratings.



\## Calibration

Calibration compares a measuring instrument with a reference standard of known accuracy. Calibration intervals

are set so that instruments stay within tolerance between checks.



\## Measurement System Analysis

MSA evaluates how much variation comes from the measurement system itself. Gage R\&R studies separate

repeatability (same operator, same instrument) from reproducibility (different operators).

