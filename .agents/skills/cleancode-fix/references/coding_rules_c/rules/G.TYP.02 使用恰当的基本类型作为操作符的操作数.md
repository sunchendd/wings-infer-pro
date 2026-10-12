# G.TYP.02 使用恰当的基本类型作为操作符的操作数

- **规则ID**：7bff4c4d-3fcc-4d09-8bb8-c738c6793598
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

严重

**【描述】**

不是所有的操作符都可以接受任意类型的操作数，有些操作符只能接受特定类型的操作数，因此，请使用符合规则的操作数类型。

**【正确示例】**

```
##### 场景1：操作数类型不符合
- 修复示例：
```c
bool b1 = false;
char c1 = 'a';
enum Color e1;
int n1;
unsigned int un1;
...
b1 = (c1 == 'A');       // 符合
b1 = (e1 == RED);       // 符合
b1 = (n1 != -1);        // 符合
b1 = (un1 < MAX_LEN);   // 符合
```


```
**【错误示例】**

```
##### 场景1：操作数类型不符合
- 错误示例：
```c
bool b1 = false;
char c1 = '1';
enum eN1 e1;
int n1;
unsigned int un1;
...
b1 = !c1;   // 不符合：操作符'!'的操作数不能使用'字符'
b1 = !e1;   // 不符合：操作符'!'的操作数不能使用'枚举'
b1 = !n1;   // 不符合：操作符'!'的操作数不能使用'有符号数'
b1 = !un1;  // 不符合：操作符'!'的操作数不能使用'无符号数'
```


```
**【修复建议】**

各类操作符的操作数的类型要求可参考以下表格（"Y"表示允许使用，"N"表示不能使用）：

<table style="font-size:0.75em; text-align:center;">

<tr><th> 操作符 </th><th> 操作数 </th><th> 布尔 </th><th> 字符 </th><th> 枚举 </th><th> 有符号数 </th><th> 无符号数 </th><th> 浮点数 </th><th> 指针 </th></tr>

<tr><td style="text-align:left;"> [ ] </td><td> 操作数 </td><td> N </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> N </td><td> N </td></tr>

<tr><td style="text-align:left;"> 一元+、一元- </td><td> 操作数 </td><td> N </td><td> N </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> N </td></tr>

<tr><td style="text-align:left;"> 一元++、一元-- </td><td> 任意操作数 </td><td> N </td><td> Y </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td></tr>

<tr><td style="text-align:left;"> 二元+、二元-、<br> +=、-=</td><td> 任意操作数 </td><td> N </td><td> Y </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td></tr>

<tr><td style="text-align:left;"> 二元*、/、<br> /=、*=</td><td> 任意操作数 </td><td> N </td><td> N </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> N </td></tr>

<tr><td style="text-align:left;"> %=、% </td><td> 任意操作数 </td><td> N </td><td> N </td><td> N </td><td> Y </td><td> Y </td><td> N </td><td> N </td></tr>

<tr><td style="text-align:left;"> <<=、>>=、<br> <<、>> </td><td> 任意操作数 </td><td> N </td><td> N </td><td> N </td><td> N </td><td> Y </td><td> N </td><td> N </td></tr>

<tr><td style="text-align:left;"> >、<、<=、>= </td><td> 任意操作数 </td><td> N </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td></tr>

<tr><td style="text-align:left;"> ==、!= </td><td> 任意操作数 </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td><td> Y </td><td> N </td><td> Y </td></tr>

<tr><td style="text-align:left;"> 二元&、~、|、^、<br> |=、 ^=、 &=、 </td><td> 任意操作数 </td><td> N </td><td> N </td><td> N </td><td> N </td><td> Y </td><td> N </td><td> N</td></tr>

<tr><td style="text-align:left;"> !、&&、|| </td><td> 任意操作数 </td><td> Y </td><td> N </td><td> N </td><td> N </td><td> N </td><td> N </td><td> Y </td></tr>

<tr><td style="text-align:left;"> ?: </td><td> 第一操作数 </td><td> Y </td><td> N </td><td> N </td><td> N </td><td> N </td><td> N </td><td> Y </td></tr>

</table>

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
