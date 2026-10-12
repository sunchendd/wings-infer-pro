# G.TYP.03 不要使用难以理解的字面量

- **规则ID**：7530bc7f-03c5-45a1-8621-908c0a4c5ddc
- **更新时间**：2025-06-05 04:15:03

---

**【问题级别】**

一般

**【描述】**

难以理解的字面量是指通过代码的上下文难以明确业务含义的字面量，包括整型字面量、浮点数字面量、布尔字面量和字符串字面量等。使用难以理解的字面量，会导致代码难以维护和阅读。

**【正确示例】**

```
【正例】 下代码中，提取出了能表达含义的常量并通过标识符命名来解释数字含义。

ACTION_1 = "action1" # 行为模式1
def run():
    prepare(ACTION_1)
    execute(ACTION_1)
    release(ACTION_1)
【正例】
装饰器中的重复字符串在上下文中是能够理解其含义的，可以不抽取为常量字符串。

@app.route("/api/users",methods=['GET','POST','PUT'])
def users():
    pass
@app.route("/api/projects/",methods=['GET','POST','PUT'])
def projects():
    pass

```
**【错误示例】**

```
【反例】

def run():
    prepare("this is a duplicate")  # 不符合 ，字符串"this is a duplicate" 多次使用，且难以理解信息
    execute("this is a duplicate")
    release("this is a duplicate")

```
**【修复建议】**

提取重复出现的字符串常量
