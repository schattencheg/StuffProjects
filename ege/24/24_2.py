'''
https://inf-ege.sdamgia.ru/problem?id=85700

    Текстовый файл состоит из десятичных цифр и заглавных букв латинского алфавита. 
    Определите в прилагаемом файле минимальное количество идущих подряд символов, 
        среди которых буква T встречается ровно 63 раза, гласная буква встречается ровно один раз, 
        искомая последовательность заканчивается на эту единственную гласную букву.
        В ответе запишите число – количество символов в найденной последовательности.
    Примечание: A, E, I, O, U, Y  — гласные буквы латинского алфавита.
'''

import os


input_dir = 'input'
filename = '24_1.txt'
filename = os.path.join(input_dir, filename)

s = open(filename).readline().strip()
# Заменим все главсные на букву А
s = s.replace('E', 'A').replace('I', 'A').replace(
    'O', 'A').replace('U', 'A').replace('Y', 'A').replace('A', 'A*')

words = s.split('*')
min_len = float('inf')
for word in words:
    if word.count('T') == 63:
        min_len = min(min_len, len(word) + 1)
print(min_len)
