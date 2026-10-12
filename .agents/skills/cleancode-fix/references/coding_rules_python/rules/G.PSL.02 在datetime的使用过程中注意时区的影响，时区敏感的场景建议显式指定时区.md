# G.PSL.02 在datetime的使用过程中注意时区的影响，时区敏感的场景建议显式指定时区

- **规则ID**：fc370eaa-65f0-4768-84df-6c4399edbbe0
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

`datetime`标准库在未指定`tz`可选参数时，会按照操作系统设置的时区显示时间。未显式指定时区的软件在跨时区使用时，会因为不同的系统时区设置导致预期外的问题。在涉及时间比较和时间差计算等场景，在夏令时切换时，系统时区的时间会发生跳变，使用系统时区的时间可能会导致预期外的问题。

**【正确示例】**

```
### 场景1：datetime的使用
- 修复示例：使用带时区的时间
```python
from datetime import datetime, timezone


def main():
    print(datetime.now(tz=timezone.utc))  # 2021-04-02 15:04:31.759787+00:00，推荐该用法，包含明确的时区信息
    print(datetime.now(tz=timezone.utc).tzname())  # UTC
    print(datetime.utcnow())  # 2021-04-02 15:04:31.759787


if __name__ == '__main__':
    main()
```

- 修复示例：通过utc时间获取中国当地时间
```python
from  datetime import datetime, timezone, timedelta


def main():
    utc_time = datetime.now(tz=timezone.utc)  # UTC
    local_time = utc_time + timedelta(hours=8)  # 中国本地时间
    print(utc_time,local_time)

if __name__ == '__main__':
    main()
```

```
**【错误示例】**

```
### 场景1：datetime的使用
- 错误示例：直接使用本地时间
```python
from datetime import datetime


def main():
    print(datetime.now())  # 2021-04-02 15:04:31.759787 比UTC时间快8小时
    print(datetime.now().tzname())  # None


if __name__ == '__main__':
    main()
```

```python
import datetime
import time

LIFETIME = datetime.timedelta(hours=6)


class TokenExpired(Exception):
    pass


def validate_token_lifetime(token_signed_at):
    """判断token是否过期"""
    if datetime.timedelta(0) < datetime.datetime.now() - token_signed_at < LIFETIME:
        return
    raise TokenExpired()


if __name__ == '__main__':
    # 以下为演示代码，环境时区为德国柏林CEST
    # 在2021-10-31 03:00会结束夏令时，时间跳变为02:00
    # 可在linux环境复现 export TZ='Europe/Berlin'; date -s "2021-10-31 02:55 CEST"
    test_date = datetime.datetime.now()  
    print(test_date)  # 2021-10-31 02:55:40.782425
    validate_token_lifetime(test_date)  # None
    time.sleep(300)  # 等待夏令时切换
    # 此时认证会抛出TokenExpired异常，而实际上此时没有超出有效期
    validate_token_lifetime(test_date)
```

```
**【修复建议】**

使用`datetime`标准库时，显式指定`tz`可选参数为希望使用的时区。使用`UTC`时间时建议直接使用`datetime.now(tz=timezone.utc)`方式。
