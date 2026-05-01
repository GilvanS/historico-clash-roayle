import pandas as pd

def diag_xx():
    df = pd.read_csv('src/data_csv_oficial/oponentes_ano_2024.csv')
    xx = df[df['tag_oponente'] == '#2YUG0LGP8']
    print("Registros X_X em 2024:")
    print(xx[['data', 'tag_oponente', 'resultado']])
    
    xx['data_dt'] = pd.to_datetime(xx['data'], dayfirst=True)
    if len(xx) >= 2:
        recs = xx.to_dict('records')
        d1 = recs[0]['data_dt']
        d2 = recs[1]['data_dt']
        diff = (d2 - d1).total_seconds()
        print(f"Diff: {diff}s")
        print(f"Match TZ condition: {abs(diff - 10800) < 600}")

if __name__ == "__main__":
    diag_xx()
