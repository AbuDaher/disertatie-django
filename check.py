import pandas as pd

df = pd.read_csv('sample_data/products_training.csv')
print('Rânduri:', len(df), '← trebuie 1200')
print('Succes%:', round(df['commercial_success'].mean()*100,1), '← trebuie ~41%')
print('Categorii:', len(df['category'].unique()), '← trebuie 10')
print('Categorii lista:', sorted(df['category'].unique()))