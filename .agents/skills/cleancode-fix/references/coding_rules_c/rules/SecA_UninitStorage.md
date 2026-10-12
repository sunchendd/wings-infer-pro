# SecA_UninitStorage

- **规则ID**：897a50ec-cf7b-4f45-a487-ac6be4e11755
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查未初始化内存的使用

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;1.检查未初始化变量参与二目运算；
2.检查未初始化变量参与单目运算；
3.检查未初始化变量最为函数参数【Example】&nbsp;&nbsp;void good(){
   int a = 0;
   int c = a;
   c++;
}void bad1(){
   int a;
   int b =a;//a未初始化，告警
   a++;//a未初始化，告警
}

void bad2_test(int a){};
void bad2(){
   int a;
   bad2_test(a);//a未初始化，作为函数参数，告警
}

```
**【修复建议】**

对未初始化的变量进行初始化







int result;



int uninit_example2(int c) {



        int *x;



        if(c)



                x = &c;



        use (x); //跨函数使用未初始化变量*x,if(c)的else也需要初始化x



}



void use (int *x) {



        result = *x+2;



}
