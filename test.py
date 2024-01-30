import datetime
start = datetime.datetime.now()
i = 1
while True:
    is_answer = True
    for j in range(1, 20):
        if i % j != 0:
            is_answer = False
            break
    if is_answer:
        break
    i += 1
print(i)
end = datetime.datetime.now()
print((end - start).seconds)