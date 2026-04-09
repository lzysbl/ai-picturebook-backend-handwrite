def app(fun):# 装饰器函数，接受一个函数作为参数
    def x():
        print("before")
        fun()
        print("after")
    return x

@app
def hello():
    print("hello world")

if __name__ == "__main__":
    hello()