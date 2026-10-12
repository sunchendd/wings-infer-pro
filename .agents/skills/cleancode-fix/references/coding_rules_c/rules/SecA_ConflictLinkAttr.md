# SecA_ConflictLinkAttr

- **规则ID**：8bb076ee-bc8b-4a5a-a26e-8b59b927b9cb
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

不要声明具有冲突链接属性的标识符，在同一个编译单元中，如果某个标识符同时兼具内部和外部链接，则行为是未定义的。

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;定位到变量定义以及函数定义：1.第一次声明是static链接方式，第二次未声明链接方式，告警；2.第一次未声明链接方式，第二次声明是static链接方式，告警；3.第一次声明是extern，第二次声明是static，告警；4.第一次声明是extern，第二次未声明，告警【Example】&nbsp;&nbsp;//good example

// 如下正确代码示例，不包含冲突的声明或定义：
static int x = 0;
static int x;           
static int Func(void);
static int Func(void)   
{
    return 1;
}



//bad example

static int i2 = 0;
int i2;   // potential flaw: static 无 未定义 


static int i3;
extern i3;  //// potential flaw: static extern 内部链接. 但是这样定义不是很好，还是告警


int i4 = 0;
static int i4; // potential flaw: 无 static 未定义

extern int i8 = 0;
int i8;   // potential flaw: extern 无 未定义

```
**【修复建议】**

<p>保持链接属性标识符的一致性，参考以下对象链接方式：

第一次声明 第二次声明 链接性

static &nbsp; &nbsp; static &nbsp; &nbsp;内部链接

static &nbsp; &nbsp; 无 &nbsp; &nbsp; &nbsp; &nbsp;未定义

static &nbsp; &nbsp; extern &nbsp; &nbsp;内部链接

无 &nbsp; &nbsp; &nbsp; &nbsp; static &nbsp; &nbsp;未定义

无 &nbsp; &nbsp; &nbsp; &nbsp; 无 &nbsp; &nbsp; &nbsp; &nbsp;无链接

无 &nbsp; &nbsp; &nbsp; &nbsp; extern &nbsp; &nbsp;外部链接

extern &nbsp; &nbsp; static &nbsp; &nbsp;未定义

extern &nbsp; &nbsp; 无 &nbsp; &nbsp; &nbsp; &nbsp;未定义

extern &nbsp; &nbsp; extern &nbsp; &nbsp;外部链接</p>
