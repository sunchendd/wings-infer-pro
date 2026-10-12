# G.ARR.03 禁止通过对指针变量进行sizeof操作来获取数组大小

- **规则ID**：7c3fe96c-cc7d-48d5-a89b-2f204210854d
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

将指针当做数组进行sizeof操作时，会导致实际的执行结果与预期不符。例如：变量定义 char *p = array，其中array的定义为char array[LEN]，表达式sizeof(p)得到的结果与 sizeof(char *)相同，并非array的长度。

**【正确示例】**

```
如下代码示例中，将sizeof(buffer)修改为申请的缓冲区大小：

char path[MAX_PATH];
char *buffer = (char *)malloc(SIZE);
...
...
memset(path, 0, sizeof(path));
memset(buffer, 0, SIZE); // 使用申请的缓冲区大小

```
**【错误示例】**

```
如下代码示例中，buffer和path分别是指针和数组，程序员想对这2个内存进行清0操作，但由于程序员的疏忽，将内存大小误写成了sizeof(buffer)，与预期不符。

char path[MAX_PATH];
char *buffer = (char *)malloc(SIZE);
...
...
memset(path, 0, sizeof(path));
// sizeof与预期不符，其结果为指针本身的大小而不是缓冲区大小
memset(buffer, 0, sizeof(buffer));

```
**【修复建议】**

禁止通过对指针变量进行sizeof操作来获取数组大小
