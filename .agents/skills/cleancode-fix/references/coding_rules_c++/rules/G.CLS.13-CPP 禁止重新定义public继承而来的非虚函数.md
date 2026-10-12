# G.CLS.13-CPP 禁止重新定义public继承而来的非虚函数

- **规则ID**：23c8f285-b038-4726-94f8-2fa882b2f90b
- **更新时间**：2025-03-25 19:22:11

---

**【问题级别】**

严重

**【描述】**

只有虚函数才能实现动态绑定：只要操作基类的指针，即可获得正确的结果。非虚函数无法实现动态绑定。在派生类中重新定义继承而来的非虚函数，增加了程序的复杂性甚至导致错误。



**【正确示例】**

```


```
**【错误示例】**

```
class Base {
public:
    void Fun() { std::cout << "Call Base Fun" << std::endl; }
};

class Derived : public Base { 
public:
    void Fun() { std::cout << "Call Derived Fun" << std::endl; }
};
Derived* d = new Derived();                     
Base* b = d;

d->Fun();                   // 调用派生类的Fun                  
b->Fun();                   // 调用基类的Fun

```
**【修复建议】**

（1）重命名函数名称；或者（2）将基类中的函数声明为虚函数
