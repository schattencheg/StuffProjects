'''
https://inf-ege.sdamgia.ru/test?theme=414

    Напишите программу, которая ищет среди целых чисел, принадлежащих числовому отрезку [174457; 174505], 
        числа, имеющие ровно два различных натуральных делителя, не считая единицы и самого числа. 
        Для каждого найденного числа запишите эти два делителя в два соседних столбца на экране с 
        новой строки в порядке возрастания произведения этих двух делителей. Делители в строке 
        также должны следовать в порядке возрастания.

    Например, в диапазоне [5; 9] ровно два различных натуральных делителя имеют числа 6 и 8, 
        поэтому для этого диапазона вывод на экране должна содержать следующие значения:

    2 3
    2 4
'''


def get_deviders(input: int) -> list[int]:
    result: list[int] = []
    for i in range(2, input // 2 + 1):
        if input % i == 0:
            result.append(i)
    return result


n_start = 174457
n_end = 174505

dividers: dict[int, list[int]] = {
    x: get_deviders(x) for x in range(n_start, n_end)}
dividers_filtered = {x: dividers[x]
                     for x in dividers.keys() if len(dividers[x]) == 2}
for x in dividers_filtered.values():
    print(f'{x[0]:<6d} {x[1]:<6d} -> {x[0] * x[1]}')
