# SecA_Overrun

- **规则ID**：1fd946c9-e62f-43d6-bd22-345c801592a6
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

严重

**【描述】**

检查数组下标越界导致的缓冲区溢出问题

**【正确示例】**

```
```
#include <cstdlib>
#define STANDARD_SIZE 100
void Func()
{
    char *p = (char*)malloc(STANDARD_SIZE);
    if (p == NULL) {
        return;
    }
    int y = 0;
    p[y] = 'a';
    free(p);
}
```

```
**【错误示例】**

```
```
#define STANDARD_SIZE 100
/*
 * @Scene: 由malloc申请内存，然后通过索引访问内存
 * @SubScene: 索引通过赋值传递，超过了上边界
 */
void TestCaseBad02()
{
    char *p = malloc(STANDARD_SIZE);
    if (p == NULL) {
        return;
    }
    int y = STANDARD_SIZE; //  Valid indices are buffer[0] to buffer[y - 1]
    /* 不符合: writing to buffer[y] overruns local buffer  */
    p[y] = 'a';
    free(p);
}
```

```
**【修复建议】**

基于业务逻辑，做出合理的数组越界检查和赋值
