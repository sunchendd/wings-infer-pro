# SecA_ClassCopy

- **规则ID**：52ecdfe0-8ae2-4df4-80a8-18dfd2f01e31
- **更新时间**：2025-03-25 19:23:48

---

**【问题级别】**

一般

**【描述】**

查找进行了继承类对象到基类对象实例的拷贝，或者在多个继承类的对象之间相互拷贝

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp; 当一个基类有继承类时，禁止从继承类对象到基类对象实例的拷贝，也不能在多个继承类的对象之间相互拷贝，这样会导致信息的丢失，程序运行异常，从而引发DOS（denial-of-service）。【Example】&nbsp;&nbsp;//good example

推荐做法1（引用）：

int main () 

{

         Employee coder("Joe Smith");

         Employee typist("Bill Jones");

         Manager designer("Jane Doe", typist);

         Employee &toPrint = designer; /* Jane remains entire */

         toPrint.print();

}

推荐做法2（使用指针）：

int main () 

{

         Employee *coder = new Employee("Joe Smith");

         Employee *typist = new Employee("Bill Jones");

         Manager *designer = new Manager("Jane Doe", *typist);

         coder = designer;

         coder->print();

}

推荐做法3（使用智能指针）：

int main () 

{

         auto_ptr<Employee> coder(new Employee("Joe Smith"));

         auto_ptr<Employee> typist(new Employee("Bill Jones"));

         auto_ptr<Manager> designer(new Manager("Jane Doe", *typist));

         coder = designer; /* Smith deleted, Doe xferred */

         coder->print();

         /* everyone deleted */

}




//bad example

错误示例：下列代码中切分了类对象，会导致数据丢失。

class Employee {

public:

         Employee(string theName): name(theName){};

         string getName() const {return name;}

         virtual void print() const

          {

                  cout << "Employee: " << getName() << endl;

         }

        virtual ~Employee()

private:

         string name;

};

class Manager: public Employee {

public:

         Manager(string theName, Employee theEmployee):Employee(theName), assistant(theEmployee) {};

         Employee getAssistant() const {return assistant;}

         virtual void print() const

          {

                  cout << "Manager: " << getName() << endl;

                  cout << "Assistant: " << assistant.getName() << endl;

         }

private:

         Employee assistant;

};

int main ()

{

         Employee coder("Joe Smith");

         Employee typist("Bill Jones");

         Manager designer("Jane Doe", typist);

         coder = designer; /* 【错误】切分了对象designer:Jane Doe */

         coder.print();

}

运行结果：Employee: Jane Doe

示例代码中基类Employee，继承类Manager（增加了属性assistant），如果将Manager类的对象数据拷贝给Employee类的对象，则将发生对象切分，Manager类的assistant属性数据将丢失。

```
**【修复建议】**

可以采取如下方式：引用；使用指针；使用智能指针。
