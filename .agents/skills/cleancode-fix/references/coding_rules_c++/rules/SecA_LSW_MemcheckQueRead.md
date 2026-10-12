# SecA_LSW_MemcheckQueRead

- **规则ID**：2cfad27b-4f34-4add-87b2-07659310a466
- **更新时间**：2025-03-25 19:23:56

---

**【问题级别】**

一般

**【描述】**

检查VOS_Que_Read读出消息队列后，消息遗漏释放造成内存泄露问题

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;检查原理:
1、函数中包含VOS_Que_Read函数调用，标记进行检查
2、匹配VOS_Que_Read，标记读出变量A
3、匹配p = A.field或p = A[i]，标记消息变量p
4、匹配消息释放，设置free状态
5、end：在路径结尾（注意for(;;)匹配不到路径结尾）或default分支的continue时，未释放消息，告警内存泄露
6、由于匹配break分支误报较多（有的是在case分支内释放、有的在case分支被调函数释放有的在break之后的公共流程释放），不对break分支进行检查【Example】&nbsp;&nbsp;//good example

void test_good1(int any,int num)
{
 STU stu;
 char *p = NULL;
 
 VOS_Que_Read(any,&stu);
 
 p = stu.name; 
 
 free(p);
 
 
 if(num > 10){                
  return;                 
 }
}



//bad example

//p在分支结束前有没有释放
void test_bad1(int any,int num)
{
 STU stu;
 char *p = NULL;
 
 VOS_Que_Read(any,&stu);   
 
 p = stu.name;    
 
 
 if(num > 10){                
  return; //leak
 }
 
 free(p);     
}

```
**【修复建议】**

分支结束前请释放申请的内存
