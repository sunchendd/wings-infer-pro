# G.FNM.06 使用return代替StopIteration来结束生成器

- **规则ID**：62db4c6f-77ff-4964-ab29-d77a5e9524b9
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

使用return代替raise StopIteration来结束生成器的迭代。从Python3.7开始，生成器退出时的StopIteration将会被解释器转换成RuntimeError。

**【正确示例】**

```
def correct_example():
    for i in range(100):
        if i == 10:
            return
        yield i


for i in correct_example():
    print(i)

```
**【错误示例】**

```
# 该生成器将不会在i等于10时正常结束返回，而是抛出一个异常
def wrong_example():
    for i in range(100):
        if i == 10:
            raise StopIteration()
        yield i


for i in wrong_example():
    print(i)

```
**【修复建议】**

用 `return` 来结束生成器的迭代。
