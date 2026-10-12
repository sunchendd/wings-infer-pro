# G.DSP.02 安全场景下必须使用密码学意义上的安全随机数

- **规则ID**：c8f008b5-7b48-4b34-9cf5-2bc354063259
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

Python的random模块实现了基于各种分布的伪随机数生成器。产生的随机数可以是均匀分布、高斯分布、对数正态分布、负指数分布以及alpha、beta分布，但是这些随机数都是伪随机数，禁止应用于安全加密目的的应用中。出于安全加密目的的应用中禁止使用random模块生成的伪随机数，必须使用安全随机数。

**【正确示例】**

```
【正例1】Python3.6以上版本的os.urandom方法以阻塞模式从系统指定的随机源获取随机字节，因此使用os.urandom方法生成随机数是安全的：
import os
import platform


# 长度请参见密码算法规范，不同场景要求长度不一样
rand_length = 16

_rand_lst = list(os.urandom(rand_length))
print(_rand_lst)
_rand_bytes = os.urandom(rand_length)
print(_rand_bytes)
注意： Python3.6以下版本中，os.urandom在linux系统环境中生成的随机数不安全，不符合我司标准。

【正例2】推荐使用secrets模块生成随机数：
import secrets


# 生成随机整数
number = secrets.randbelow(10)
print("Secure random number is ", number)
# Secure random number is 0
secrets_generator = secrets.SystemRandom()
random_number = secrets_generator.randint(0, 50)
print("Secure random number is ", random_number)
# Secure random number is 26

# 指定范围并设置步长
random_number = secrets_generator.randrange(5, 50, 5)
print("Secure random number within range is ", random_number)
# Secure random number within range is 15

# 从指定的数据集中选择
number_list = [6, 12, 18, 24, 30, 36, 42, 48, 54, 60]
secure_choice = secrets_generator.choice(number_list)
print("Secure random choice using secrets is ", secure_choice)
# Secure random choice using secrets is 30
secure_sample = secrets_generator.sample(number_list, 3)
print("Secure random sample using secrets is ", secure_sample)
# Secure random sample using secrets is [54, 6, 42]

# 随机安全浮点数
secure_float = secrets_generator.uniform(2.5, 25.5)
print("Secure random float number using secrets is ", secure_float)
# Secure random float number using secrets is 9.445927455984885

```
**【错误示例】**

```
import random


sr = random.randint(0, 100)

```
**【修复建议】**
