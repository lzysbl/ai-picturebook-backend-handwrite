a=[1]

a.append(2)

print(a)
#unicode字符串
#r表示原始字符串，\n不转义
print(r"/n")
#chr编码转字符
print(chr(65))
#ord字符转编码
print(ord('A'))
print(ord('中'))
#二进制字符串,b表示二进制字符串
print(format(1234, 'b'))
#bin函数将十进制数转换为二进制字符串
print(bin(ord('中')))
#统计字符串长度
print(len('hello world'))
#字符串编码，encode方法将字符串转换为二进制字符串
print("abc".encode('utf-8'))

#字符串解码，decode方法将二进制字符串转换为字符串
print(b"1010100".decode('utf-8'))

#字符串切片，切片的语法是[start:end:step]，start表示起始位置，end表示结束位置，step表示步长
print("hello world"[0:5])
print("hello world"[6:11])
print("hello world"[::2])
#-1表示倒数第一个字符，-2表示倒数第二个字符，以此类推
print("hello world"[-1])
print("hello world"[-2])
split_a = "hello world".split()
print(split_a[0])
#format方法格式化字符串，{}表示占位符，format方法将值填充到占位符中
print("hello {}".format("world"))
