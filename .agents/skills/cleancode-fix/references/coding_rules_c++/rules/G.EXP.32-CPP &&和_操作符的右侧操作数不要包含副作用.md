# G.EXP.32-CPP &&和||操作符的右侧操作数不要包含副作用

- **规则ID**：bfbf760b-5b30-42c2-9244-14634b006f1e
- **更新时间**：2025-03-25 19:23:16

---

**【问题级别】**

一般

**【描述】**

逻辑与（&&）、逻辑或（||）表达式中的右操作数是否被求值，取决于左操作数的求值结果，当左操作数的求值结果可以得出整个逻辑表达式的结果时，不会再计算右操作数的结果。



如果右操作数包含副作用，则不能确定是否确实发生了副作用，因此，本条款中建议逻辑与（&&）、逻辑或（||）操作符的右操作数中不要含有副作用。

**【正确示例】**

```
如下代码中，明确逻辑行为（可以将公共代码提取成函数在不同分支调用）。

if (flag > 0) {
    ...
} else {
    value--;
    if (value >= 0) {
        ...
    }
}

如下的一个解决方案是拆分if语句中的表达式：

static int RemoveFile(uint32_t fileId)
{
    std::string fileName = "/some_dir/" + std::to_string(fileId) + ".txt";

    return unlink(fileName.c_str()); // 该语句具有副作用
}

void Call()
{
    ...
    if (isRight) {
        if (RemoveFile(fileId) != 0) {
            ...
        }
    }
}

```
**【错误示例】**

```
如下代码中，当flag > 0 或 value > 0 时进入分支处理，但是 value 自减的前提是 flag <= 0。尽管代码行为是正确的，也有可能是精心设计的，但是不易阅读理解，并且给维护带来不便, 容易引入问题。

if (flag > 0 || value-- > 0) {
  ...
}

如下代码中，Call函数中的逻辑与（&&）操作符的右操作数调用了一个导致副作用的函数。

static int RemoveFile(uint32_t fileId)
{
    std::string fileName = "/some_dir/" + std::to_string(fileId) + ".txt";

    return unlink(fileName.c_str()); // 该语句具有副作用
}

void Call()
{
    ...
    if (isRight && (RemoveFile(fileId) != 0)) {
        ...
    }
}

```
**【修复建议】**

逻辑与（&&）、逻辑或（||）操作符的右操作数中不要含有副作用。副作用是指对执行状态产生影响，包括：修改对象、访问volatile对象、修改文件等
