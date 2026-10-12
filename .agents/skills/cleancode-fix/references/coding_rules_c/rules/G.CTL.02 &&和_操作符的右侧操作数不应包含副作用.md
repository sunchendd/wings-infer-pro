# G.CTL.02 &&和||操作符的右侧操作数不应包含副作用

- **规则ID**：6b490399-3d8b-42b7-b7f9-ca2378bbd24b
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

逻辑与和逻辑或运算符的右操作数不一定被执行，因此，禁止`&&`和`||`的右操作数中含有副作用。

**【正确示例】**

```
##### 场景1：逻辑与（&&）表达式中的右操作数有赋值
- 修复示例1：

```c
char *RightOperandSideEffectAssignGood01()
{
    char *p = Get();
    /* 符合:  */
    if (p == NULL) {
        p = (char *)malloc(SIZE);
        return p;
    }
    return p;
}
```
##### 场景2：逻辑与（&&）表达式中的右操作数调用了一个导致副作用的函数
- 修复示例1：

```c
const int FILENAME_LEN = 128;
static int RemoveFile(unsigned int fileId)
{
    char filename[FILENAME_LEN];
    int ret = sprintf_s(filename, FILENAME_LEN, "/some_dir/%u.txt", fileId);
    if (ret < 0) {
        return -1;
    }
    return unlink(filename); // 该语句具有副作用
}

void RightOperandSideEffectCallGood01(bool isRight, unsigned int fileId)
{
    /* 符合: */
    if (isRight) {
        if (RemoveFile(fileId) != 0) {
            return;
        }
    }
}
```
##### 场景3：逻辑与（&&）表达式中的右操作数有递减
- 修复示例1：

```c
void RightOperandSideEffectDecrementGood01(int a, int b)
{
    float x = 0.1f;
    /* 符合:  */
    if (a > 0) {
        b--;
        if (b < 0) {
            // do something
        }
        return;
    }
}
```


```
**【错误示例】**

```
##### 场景1：逻辑与（&&）表达式中的右操作数有赋值
- 错误示例1：

```c
char *RightOperandSideEffectAssignBad01()
{
    char *p = Get();
    /* 不符合: 逻辑与（&&）表达式中的右操作数赋值 */
    if ((p == NULL) && ((p = (char *)malloc(SIZE)) == NULL)) {
        // do something
        return p;
    }
    return p;
}
```
##### 场景2：逻辑与（&&）表达式中的右操作数调用了一个导致副作用的函数
- 错误示例1：

```c
const int FILENAME_LEN = 128;
static int RemoveFile(unsigned int fileId)
{
    char filename[FILENAME_LEN];
    int ret = sprintf_s(filename, FILENAME_LEN, "/some_dir/%u.txt", fileId);
    if (ret < 0) {
        return -1;
    }
    return unlink(filename); // 该语句具有副作用
}

void RightOperandSideEffectCallBad01(bool isRight, unsigned int fileId)
{
    /* 不符合: 逻辑与（&&）表达式中的右操作数调用了一个导致副作用的函数 */
    if (isRight && RemoveFile(fileId) != 0) {
        // do something
        return;
    }
}
```
##### 场景3：逻辑与（&&）表达式中的右操作数有递减
- 错误示例1：

```c
void RightOperandSideEffectDecrementBad01(int a, int b)
{
    /* 不符合: 逻辑与（&&）表达式中的右操作数递减，后面有再次使用 */
    if (a > 0 && b-- > 0) {
        // do something
        return;
    }
    int y = b;
}
```


```
**【修复建议】**

避免在`&&`和`||`的右操作数内部实现有副作用的功能语句（包括递增递减、赋值、修改文件等），因为不确定是否执行了右操作数的表达式。
