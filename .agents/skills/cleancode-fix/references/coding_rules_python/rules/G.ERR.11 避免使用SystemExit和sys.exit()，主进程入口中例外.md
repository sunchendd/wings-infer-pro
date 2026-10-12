# G.ERR.11 避免使用SystemExit和sys.exit()，主进程入口中例外

- **规则ID**：f58dd9ce-1011-45ae-876d-f6561758b0a8
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

执行`sys.exit()`与`raise SystemExit()`等价，会抛出`SystemExit`异常，这个异常应该一直向上抛出，直到进程退出。

在普通函数内调用`sys.exit()`会给调用者带来很多麻烦，应该避免这类设计。

**【正确示例】**

```
##### 场景1：捕获父子异常
- 修复示例：在__main__入口中调用sys.exit
```python
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('At least input 2 arguments')
        sys.exit(1)  # 符合，在主进程中，可以直接使用sys.exit退出
```
- 修复示例：在__main__入口调用的函数中调用sys.exit
```python
def run():
    if len(sys.argv) == 1:
        print("Usage: %s <filename> [options]" % sys.argv[0])
        sys.exit(1)   # 符合
    elif not sys.argv[1]:
        print("%s does not exist" % sys.argv[1])
        sys.exit(1)   # 符合
    else:
        sys.exit(sys.argv[1])   # 符合
        try:
            caller()
        except SystemExit as e:
            print(e)


if __name__ == '__main__':
    run()
```

```
**【错误示例】**

```
##### 场景1：捕获父子异常
- 错误示例：在普通函数内调用`sys.exit()`和`raise SystemExit`
```python
def create_resource(resource_name):
    resource_instance = resource.create(resource_name)
    if resource_instance.error_info:
        sys.exit(ERROR_CODE)  # 不符合，不合理的设计，需要调用者做资源清理
    return resource_instance


def caller():
    try:
        resource_instance = create_resource(resource_name)
    except SystemExit as e:  # 不符合，这是不好的设计和实现，此处仅用来做资源清理的示例
        log_something(e)
        delete_resource(resource_name)
        raise e
```

```
**【修复建议】**

在__main__入口或者在入口调用的函数中使用sys.exit和SystemExit。
