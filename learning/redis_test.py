import redis

r = redis.Redis(host='127.0.0.1', port=6379, db=0) # db 是redis的分区，相当于mysql的use xx
print(r.ping())  # 应返回 True