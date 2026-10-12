# G.EXP.06 避免对带位域的结构体的布局做任何假设

- **规则ID**：20a68e16-d131-4aae-afad-16713c7c9516
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

结构体中位域的存储布局是与实现相关的，虽然在每种实现中的布局是确定的，但是在不同的实现下通常不具备可移植性。

因此，不要对带位域的结构体的布局做任何假设，在对带位域的结构体赋值时，需显式指定每个位域变量的值。

**【正确示例】**

```
##### 场景1：通过下标访问给带位域的结构体赋值
- 修复示例：
```c
typedef struct {
    uint32_t offset : 16;
    uint32_t page : 8;
    uint32_t dir : 8;
} BitFrame;

void FuncGood01(void)
{
    BitFrame data = {0};
    data.offset = 0x3fu; // good，显式指定位域变量的值
    data.page = 3u;      // good，显式指定位域变量的值
}
```
##### 场景2：通过拷贝函数对带位域的结构体进行赋值
- 修复示例：
```c
typedef struct {
    uint32_t offset : 16;
    uint32_t page : 8;
    uint32_t dir : 8;
} BitFrame;

void FuncGood02(void)
{
    BitFrame addr = {0};
    unsigned char msg[LEN] = {0};
    addr.offset = msg[0]; // 符合：显式指定位域变量的值
}
```


```
**【错误示例】**

```
##### 场景1：通过下标访问给带位域的结构体赋值
- 错误示例：

```c
typedef struct {
    uint32_t offset : 16;
    uint32_t page : 8;
    uint32_t dir : 8;
} BitFrame;

void FuncBad01(void)
{
    BitFrame *data = (BitFrame *)malloc(sizeof(BitFrame));
    if (data == NULL) {
        return;
    }
    unsigned char *p = (unsigned char *)data;
    // 不符合:  对结构体赋值没有显式赋值
    p[0] = 0xffu;
}
```
##### 场景2：通过拷贝函数对带位域的结构体进行赋值
- 错误示例：
```c
typedef struct {
    uint32_t offset : 16;
    uint32_t page : 8;
    uint32_t dir : 8;
} BitFrame;

void FuncBad02(BitFrame *msg)
{
    BitFrame addr = {0};

    errno_t ret = memcpy_s(&addr, LEN, msg, LEN); // 不符合
    ...
}
```


```
**【修复建议】**

在对带位域的结构体赋值时，显式指定每个位域变量的值。
