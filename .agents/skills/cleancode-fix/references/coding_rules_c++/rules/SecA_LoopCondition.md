# SecA_LoopCondition

- **规则ID**：ea1472cd-290c-4be5-9281-6852521986d2
- **更新时间**：2025-03-25 19:23:56

---

**【问题级别】**

一般

**【描述】**

检查可能导致死循环的来自外部的循环条件（循环包括dowhile,while,for)

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;针对以下三类（p表示指针，A/B都表示变量）：1.循环条件为*p != 2或*p == 2，且p都是来自参数（包括隐式传递），则告警；2.循环条件为p1 > p2或p1 < p2或p1 == p2，且p1和p2都是来自参数（包括隐式传递）, 则告警；3.循环条件为A<B或者A>B, 且A, B都来自参数（包括隐式传递），则循环体内存在结构体强转，或指针偏移，都告警；4.循环条件为A < 2或者A>2（此处的2表示一个常量，仅为举例），不是一个范围判断（如A < 10 && A>1)，且A来自参数（包括隐式传递）则告警。5.循环条件仅为A != 2 或 A == 2（此处的2表示一个常量，仅为举例），且A来自参数（包括隐式传递），则告警【Example】&nbsp;&nbsp;//good example

void goodtest_1(int p){
 int t = 0;
 int q = 0;
 while(p > q){     //OK，q不是常数，不告警
  t = 100;
  q++;
 }
}

void goodtest_2(int a, int b){
 int t = 0;
 while(a > b && t < 10){  //ok
  t = 100;       //没有结构体强转或指针偏移
 }
}



//bad example

void badtest_1(int *p1, int *p2){
 int t = 0;
 while(p1 > p2){    // potential flaw
  t = 100;
 }
}

void badtest_2(int a, int b){
 Student stu; 
 Student *stu_ptr = &stu;
 while(a>b){       // potential flaw
  (Teacher *)stu_ptr;  //左右均来自入参，循环体内有结构体强转
 }
}

```
**【修复建议】**

<p>避免可能导致死循环的外部循环条件表达式</p>
