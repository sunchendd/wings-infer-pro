# G.ARR.05 不同类型的对象指针之间不应进行强制转换

- **规则ID**：c2419e1d-2453-4749-91bc-465183a61c35
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

严重

**【描述】**

不同类型的指针之间进行强制转换，若结果指针没有正确地对齐，就会导致程序产生未定义行为。

因此，不同类型的对象指针之间不应进行强制转换。

**【正确示例】**

```
##### 场景1：一种指针类型转换为另一种指针类型（float* 转 int32_t*）。
- 修复示例：不同类型的对象指针之间不应进行强制转换，应该使用相同类型的指针。

```c
void Fun()
{
    float f;
    float *fPtr = &f;                   // 符合：使用相同类型指针
}

void Foo(float *p);                     // 修改参数类型
void Bar(void)
{
    float f;
    Foo(&f);                            // 符合：使用相同类型指针
}
```
##### 场景2：一种指针类型转换为另一种指针类型（int32_t* 转int16_t*）。
- 修复示例：

```c
void Use(int32_t *p)        // 修改参数类型
{
    ...
}

void Foo()
{
    int32_t val = ...;
    Use(&val);              // 符合：使用相同类型指针
}
```
- 修复示例：

```c
void Use(int16_t *p)
{
    ...
}

void Foo()
{
    int32_t val = ...;
    if (CheckRange(val)) {
        int16_t sval = (int16_t)val;    // 先校验变量范围再转换，防止转换后数据丢失
        Use(&sval);                     // 符合：使用相同类型指针
    }
}
```


```
**【错误示例】**

```
##### 场景1：一种指针类型转换为另一种指针类型（float* 转 int32_t*）。
- 错误示例：

```c
void Fun()
{
    float f;
    int32_t *intPtr = (int32_t *)&f;    // 不符合：float* 转 int32_t*
}

void Foo(int32_t *p);
void Bar(void)
{
    float f;
    Foo(&f);                            // 不符合：float* 转 int32_t*
}
```
##### 场景2：一种指针类型转换为另一种指针类型（int32_t* 转int16_t*）。
- 错误示例：

```c
void Use(int16_t *p)
{
    ...
}

void Foo()
{
    int32_t val = ...;
    Use(&val);              // 不符合：int32_t* 转int16_t*
}
```


```
**【修复建议】**

应该使用相同类型的指针。
