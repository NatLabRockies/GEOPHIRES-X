# Monte Carlo User Guide

## Example Setup

Create a project with the following structure, including GEOPHIRES in `requirements.txt` and setting up `venv` with `virtualenv`:

```
├── GEOPHIRES-example1.txt
├── MC_GEOPHIRES_Settings_file.txt
├── main.py
├── requirements.txt
└── venv/
```

In `main.py`:

```python
from pathlib import Path

from geophires_monte_carlo import GeophiresMonteCarloClient, MonteCarloResult, MonteCarloRequest, SimulationProgram


def monte_carlo():
    client = GeophiresMonteCarloClient()

    result: MonteCarloResult = client.get_monte_carlo_result(
        MonteCarloRequest(
            SimulationProgram.GEOPHIRES,

            # Files from tests/geophires_monte_carlo_tests - copy these into the same directory as main.py
            Path('GEOPHIRES-example1.txt').absolute(),
            Path('MC_GEOPHIRES_Settings_file.txt').absolute(),
            output_file=Path('MC_GEOPHIRES_Result.txt').absolute()
        )
    )

    with open(result.output_file_path, 'r') as result_output_file:
        result_display = result_output_file.read()
        print(f'MC result:\n{result_display}')

if __name__ == '__main__':
    monte_carlo()
```

To run:
```
(venv) python main.py

[...]

[2024-02-09 07:47:18][INFO] Complete geophires_monte_carlo.MC_GeoPHIRES3: main
MC result:
Electricity breakeven price, Project NPV, Gradient 1, Reservoir Temperature, Utilization Factor, Ambient Temperature
38.81, -42.59, (Gradient 1:30.09736131122952;Reservoir Temperature:320.2888549098197;Utilization Factor:0.9295528406892491;Ambient Temperature:20.684620766378806;)
17.81, -42.76, (Gradient 1:39.47722802709689;Reservoir Temperature:306.71578141214087;Utilization Factor:0.7604874092668568;Ambient Temperature:20.39891267899405;)
9.91, -41.95, (Gradient 1:50.24142993501238;Reservoir Temperature:311.3876336705825;Utilization Factor:0.8657162766204807;Ambient Temperature:20.205604589516913;)
61.37, -43.34, (Gradient 1:28.230745766883796;Reservoir Temperature:324.25115143107104;Utilization Factor:0.8308351836890867;Ambient Temperature:20.615118153663598;)
8.76, -41.76, (Gradient 1:54.66070153603035;Reservoir Temperature:319.6097066730564;Utilization Factor:0.855785650134492;Ambient Temperature:19.359218133245772;)
7.58, -37.63, (Gradient 1:57.53774721757885;Reservoir Temperature:318.6354560118773;Utilization Factor:0.9305717468323405;Ambient Temperature:20.011047903204176;)
9.35, -41.03, (Gradient 1:51.20593175130416;Reservoir Temperature:311.40737612727423;Utilization Factor:0.8876035819161642;Ambient Temperature:19.968497775278948;)
18.11, -42.68, (Gradient 1:38.66016637029756;Reservoir Temperature:310.20708430352124;Utilization Factor:0.7640202889998118;Ambient Temperature:18.805190553693578;)
10.07, -40.41, (Gradient 1:47.876595779164845;Reservoir Temperature:310.4061695000305;Utilization Factor:0.9228147348375185;Ambient Temperature:20.119411582814514;)
23.08, -41.38, (Gradient 1:33.342513206728185;Reservoir Temperature:305.48937077249826;Utilization Factor:0.9361923986407424;Ambient Temperature:18.423715643246567;)
Electricity breakeven price:
     minimum: 7.58
     maximum: 61.37
     median: 13.94
     average: 20.48
     mean: 20.48
     standard deviation: 16.36
bin values (as percentage): [0.09295408 0.18590816 0.18590816 0.         0.         0.
 0.         0.         0.         0.18590816 0.         0.
 0.         0.         0.09295408 0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.09295408
 0.         0.         0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.09295408]
bin edges: [ 7.58    8.6558  9.7316 10.8074 11.8832 12.959  14.0348 15.1106 16.1864
 17.2622 18.338  19.4138 20.4896 21.5654 22.6412 23.717  24.7928 25.8686
 26.9444 28.0202 29.096  30.1718 31.2476 32.3234 33.3992 34.475  35.5508
 36.6266 37.7024 38.7782 39.854  40.9298 42.0056 43.0814 44.1572 45.233
 46.3088 47.3846 48.4604 49.5362 50.612  51.6878 52.7636 53.8394 54.9152
 55.991  57.0668 58.1426 59.2184 60.2942 61.37  ]
Project NPV:
     minimum: -43.34
     maximum: -37.63
     median: -41.86
     average: -41.55
     mean: -41.55
     standard deviation: 1.56
bin values (as percentage): [0.87565674 0.         0.         0.         0.         1.75131349
 0.87565674 0.         0.         0.         0.         0.
 0.87565674 0.87565674 0.         0.         0.         0.87565674
 0.         0.         0.87565674 0.         0.         0.
 0.         0.87565674 0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.         0.         0.         0.         0.
 0.         0.87565674]
bin edges: [-43.34   -43.2258 -43.1116 -42.9974 -42.8832 -42.769  -42.6548 -42.5406
 -42.4264 -42.3122 -42.198  -42.0838 -41.9696 -41.8554 -41.7412 -41.627
 -41.5128 -41.3986 -41.2844 -41.1702 -41.056  -40.9418 -40.8276 -40.7134
 -40.5992 -40.485  -40.3708 -40.2566 -40.1424 -40.0282 -39.914  -39.7998
 -39.6856 -39.5714 -39.4572 -39.343  -39.2288 -39.1146 -39.0004 -38.8862
 -38.772  -38.6578 -38.5436 -38.4294 -38.3152 -38.201  -38.0868 -37.9726
 -37.8584 -37.7442 -37.63  ]

```

You may also run from the command line:

```
python -mgeophires_monte_carlo GEOPHIRESv3.py GEOPHIRES-example1.txt MC_GEOPHIRES_Settings_file.txt MC_GEOPHIRES_Result.txt
```

## Documentation

See [module documentation](reference/geophires_monte_carlo.html)

## Web Interface

Monte Carlo is available in the web interface at [gtp.scientificwebservices.com/monte-carlo](https://gtp.scientificwebservices.com/monte-carlo)
