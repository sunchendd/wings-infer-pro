# G.OTH.04 禁止在发布版本中输出对象或函数的地址

- **规则ID**：bc3d872e-0156-42c9-b407-a5dd92317400
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

高级持续性攻击（APT）通常要获取目标程序的对象或函数地址，再通过修改特定内容达到攻击目的。



内存地址信息泄露绕过了ASLR的安全防御，降低了攻击者的攻击难度。



因此，禁止在发布版本中输出对象或函数的地址。

<br>

**【正确示例】**

```
##### 场景1：格式化函数中用%p打印地址。
- 修复示例：删除打印地址的代码。

```c
int Encode(unsigned char *in, size_t inSize, unsigned char *out, size_t maxSize)
{
    ...
    // 符合：没有打印地址
    Log("in size=%zu, max size=%zu
", inSize, maxSize);
    ...
}
```
##### 场景2：格式化函数中用%d打印intptr_t或uintptr_t整型。
- 修复示例1：如果intptr_t或uintptr_t整型变量保存的是地址，删除打印地址的代码。

```c
int Encode(intptr_t in, size_t inSize)
{
    ...
    // 符合：没有打印地址
    Log("in size=%zu", inSize);
    ...
}
```
- 修复示例2：如果intptr_t或uintptr_t整型变量保存的不是地址，应该修改变量类型，修改后的类型名和地址无关。

```c
int Encode(int in, size_t inSize)
{
    ...
    // 符合：没有打印地址
    Log("in=%d, in size=%zu", in, inSize);
    ...
}
```
- 修复示例3：将地址转换为hash值再打印。

```c
略
```


```
**【错误示例】**

```
##### 场景1：格式化函数中用%p打印地址。
- 错误示例：

```c
int Encode(unsigned char *in, size_t inSize, unsigned char *out, size_t maxSize)
{
    ...
    // 不符合：用%p打印地址
    Log("in=%p, in size=%zu, out=%p, max size=%zu
", in, inSize, out, maxSize);
    ...
}
```
##### 场景2：格式化函数中用%d打印intptr_t或uintptr_t整型。
- 错误示例：

```c
int Encode(intptr_t in, size_t inSize)
{
    ...
    // 不符合：打印地址
    Log("in=%d, in size=%zu", in, inSize);
    ...
}
```


```
**【修复建议】**

禁止在发布版本中输出对象或函数的地址。

1. 对于格式化函数中用%p打印地址的场景，删除打印地址的代码。

2. 对于格式化函数中用%d、%x、%o等打印intptr_t或uintptr_t整型的场景，

2.1 如果intptr_t或uintptr_t整型变量保存的是地址，删除打印地址的代码。

2.2 如果intptr_t或uintptr_t整型变量保存的不是地址，应该修改变量类型，修改后的类型名和地址无关。

3. 将地址转换为hash值再打印。
