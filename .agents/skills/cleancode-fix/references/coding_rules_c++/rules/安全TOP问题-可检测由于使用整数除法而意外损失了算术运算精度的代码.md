# 安全TOP问题-可检测由于使用整数除法而意外损失了算术运算精度的代码

- **规则ID**：67b23b4c-0535-4dac-9de8-b8e38da1ec04
- **更新时间**：2025-03-25 19:24:01

---

**【问题级别】**

严重

**【描述】**

可检测由于使用整数除法（可能原本要使用浮点除法）而意外损失了算术 运算精度的代码。

**【正确示例】**

```
void Goodtest01(double a, double b){
    float m = a/b;   //OK
}

```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;1.定位到"及"="二元操作符
2.检查左右表达式的类型，是否是整数型
3.检查此二元表达式是否被隐式转换为浮点数类型
4.检查左右表达式相除是否有余数，有则告警，没有不告警，，舍入【Example】&nbsp;&nbsp;//被除数和除数都是浮点数
void goodTest_1(double a, double b){
 float m = a/b;   //OK
}

//整除，不告警
void goodTest_2(){
 long long a = 1000;
 unsigned short b = 10;
 float m = a/b;  //OK，整除
}//bad
void badTest(){
 // Sets PI_APPROX to 3.0!
 double PI_APPROX = 22 / 7; // err
}

```
**【修复建议】**

检查代码是否存在笔误；检查代码逻辑，若为逻辑错误，则修改逻辑，删除无效代码







下面例子中2个整数相除得出的还是整数22/7=3，应该定义double a=22,b=7,double PI_APPROX = a / b



double PI_APPROX = 22 / 7; // Defect







下面例子中2个整数相除得出的还是整数，应该定义double a, double  b



int roundedAverage(int a, int b) {



        return (int)(0.5 + ((a + b) / 2)); // Defect



}
