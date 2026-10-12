# G.FUU.03 调用格式化输入/输出函数时，使用有效的格式字符串

- **规则ID**：6786f8bc-ca5d-4c5d-831d-1053144ceead
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

格式化输入/输出函数是根据格式字符串来解析和处理数据，因此使用有效的格式字符串非常重要。这不仅确保了数据能够正确地被读取或显示，同时也能够避免潜在的编程错误和安全问题，例如缓冲区溢出。



使用格式字符串时，应确保format参数与实际参数的**类型**和**个数**一致，且**宽度/精度说明符**、**缓冲区长度参数**必须正确使用。



规则覆盖的格式化函数包括：



- 格式化输入函数

```c 

// 标准字符输入

scanf, scanf_s, fscanf, fscanf_s, sscanf, sscanf_s, _scanf_l, _snscanf_s



// 宽字符输入

wscanf, wscanf_s, fwscanf_s, swscanf_s, _wscanf_l



// 自定义输入

VOS_scanf_s, VOS_fscanf_s, VOS_sscanf_s, VOS_wscanf_s, VOS_fwscanf_s, VOS_swscanf_s, VOS_sscanf_Safe

```



- 格式化输出函数

```c

// 标准字符输出

printf, fprintf, sprintf, sprintf_s, snprintf, snprintf_s, _sprintf_l,  _snprintf, _snprintf_s



// 宽字符输出

swprintf, swprintf_s, _swprintf_l, __swprintf_l, _snwprintf_s



// 自定义输出

VOS_sprintf_s, VOS_snprintf_s, VOS_swprintf_s, VOS_nsprintf_Safe

```



- 对于其他自定义的格式化函数，需要通过添加模型配置后，才能被规则检查

**【正确示例】**

```
##### 场景1：format参数个数与实际参数个数不一致
- 修复示例1：输出缓冲区参数个数正确
```c
int d;
int d2;
int ret = sscanf_s(src, "%d %d", &d, &d2);
```
- 修复示例2：输出缓冲区参数个数正确
```c
int d;
int ret = sscanf_s(src, "%d", &d);
```
- 修复示例3：输入函数中，%*[width] [{h | l | I64 | L}]type 表示满足该条件的被过滤掉，不会向目标参数中写入值
```c
int ulYear, ulMonth, ulDay, b;
sscanf_s(acTemp, "%u-%u-%u%*s", &ulYear, &ulMonth, &ulDay); // "%*s" 不需要可变参数
```
- 修复示例4：输出函数中，"*"用来占用一个本来需要一个指定宽度或精度的常数数字的位置
```c
sprintf(s, "%.*s%.*s", sizeof(a1), a1, sizeof(a2), a2); //  "%.*s%.*s" 对应4个可变参数
```
- 修复示例5：使用格式串%s、%S、%c、%C或括号表达式（例如%[a-d]）时，添加入参“输出缓冲区对应长度参数”
```c
char token[16] = {0};
int ret = sscanf_s(string, "%s", token, sizeof(token)); // sizeof(token)对应长度参数
//或
char c;
int ret = sscanf_s(string, "%c", &c, 1); // 1对应长度参数
```
##### 场景2：format中转换指示符与实参类型不匹配
- 修复示例：正确的做法是确保printf()函数的实参匹配format的转换指示符。

```c
void Foo(void)
{
    const char *infoMsg = "Information seed to user.";
    int infoLevel = 3;
    ...
    printf("infoLevel: %d, infoMsg: %s
", infoLevel, infoMsg); // 符合
    ...
}
```
##### 场景3：scanf系列函数中包含了%s、%S、%c、%C或括号表达式（例如%[a-d]）时, 宽度说明符大于或等于缓冲区实际长度，以及缓冲区长度参数大于缓冲区实际长度
- 修复示例1：宽度说明符小于缓冲区token的实际长度
```c
char token[16] = {0};
int ret = sscanf_s(string, "%15s", token, sizeof(token)); // "%15s"表示宽度说明符为15
```
- 修复示例2：缓冲区长度参数为sizeof(token)，等于缓冲区token的实际长度
```c
char token[16] = {0};
int ret = sscanf_s(string, "%s", token, sizeof(token));
```
- 修复示例3：对于wchar_t类型不应该传sizeof(数组)，应该是数组元素个数
```c
wchar_t wtoken[16] = {0};
int ret1 = sscanf_s(buffer, "%15ls", wtoken, 16); // 宽度说明符15， 缓冲区长度参数16
```
- 修复示例4：使用单字节格式化符对应char参数类型时，宽度说明符和缓冲区长度参数等于1
```c
char c;
int ret = sscanf_s(string, "%1c", &c, 1);
```
- 修复示例5：使用宽字节格式化符对应wchar_t参数类型时，宽度说明符和缓冲区长度参数等于1
```c
wchar_t wc;
int ret = sscanf_s(buffer, "%1lc", &wc, 1);
```

```
**【错误示例】**

```
##### 场景1：format参数个数与实际参数个数不一致
- 错误示例1：输出缓冲区参数个数不足
```c
int d;
int ret = sscanf_s(src, "%d %d", &d); // "%d %d"需要2个可变参数
```
- 错误示例2：输出缓冲区参数个数过多
```c
int d;
int d2;
int ret = sscanf_s(src, "%d", &d, &d2); // "%d" 只需要1个可变参数
```
- 错误示例3：输入函数中，%*[width] [{h | l | I64 | L}]type 表示满足该条件的被过滤掉，不会向目标参数中写入值
```c
int ulYear, ulMonth, ulDay, b;
sscanf_s(acTemp, "%u-%u-%u%*s", &ulYear, &ulMonth, &ulDay, &b); // "%*s" 不需要可变参数
```
- 错误示例4：输出函数中，"*"用来占用一个本来需要一个指定宽度或精度的常数数字的位置
```c
sprintf(s, "%.*s%.*s", a1, a2); // "%.*s%.*s" 需要4个可变参数
```
- 错误示例5：使用格式串%s、%S、%c、%C或括号表达式（例如%[a-d]）时，缺少入参“输出缓冲区对应长度参数”
```c
char token[16] = {0};
int ret = sscanf_s(string, "%s", token); // token后缺少缓冲区长度参数
//或
char c;
int ret = sscanf_s(string, "%c", &c); // &c后缺少缓冲区长度参数
```
##### 场景2：format中转换指示符与实参类型不匹配
- 错误示例：如下代码示例中，printf()的实参infoLevel类型与对应的转换指示符's'不匹配，正确的转换指示符要使用'd'。同样，实参infoMsg类型与对应的转换指示符'd'不匹配，正确的转换指示符要使用's'。
这些用法会使程序产生未定义行为，比如：printf()将把infoLevel实参解释为指针，试图从infoLevel包含的地址中读取一个字符串，从而发生非法访问。

```c
void Foo(void)
{
    const char *infoMsg = "Information seed to user.";
    int infoLevel = 3;
    ...
    printf("infoLevel: %s, infoMsg: %d
", infoLevel, infoMsg); // 不符合
    ...
}
```
##### 场景3：scanf系列函数中包含了%s、%S、%c、%C或括号表达式（例如%[a-d]）时, 宽度说明符大于或等于缓冲区实际长度，以及缓冲区长度参数大于缓冲区实际长度
- 错误示例1：宽度说明符等于缓冲区token的实际长度
```c
char token[16] = {0};
int ret = sscanf_s(string, "%16s", token, sizeof(token)); // "%16s" 表示宽度说明符为16
```
- 错误示例2：缓冲区长度参数大于缓冲区token的实际长度
```c
char token[16] = {0};
int ret = sscanf_s(string, "%s", token, 32); // 缓冲区长度参数为32
```
- 错误示例3：对于wchar_t类型不应该传sizeof(数组)，应该是数组元素个数 
```c
wchar_t wtoken[16] = {0};
int ret1 = sscanf_s(buffer, "%32ls", wtoken, sizeof(wtoken)); // 32是sizeof(wtoken)的值
```
- 错误示例4：使用单字节格式化符对应char参数类型时,宽度说明符或缓冲区长度参数大于1 
```c
char c;
int ret = sscanf_s(string, "%2c", &c, 2);
```
- 错误示例5：使用宽字节格式化符对应wchar_t参数类型时,宽度说明符或缓冲区长度参数大于1 
```c
wchar_t wc;
int ret = sscanf_s(buffer, "%2lc", &wc, 2);
```

```
**【修复建议】**

1、确保Format中的参数与实际参数的类型与个数一致；

2、确保宽度说明符、缓冲区长度参数使用正确。
