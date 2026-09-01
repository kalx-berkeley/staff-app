import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';

const markdownComponents: Components = {
  a: ({ children }) => <>{children}</>,
  img: () => null,
};

interface MarkdownContentProps {
  content: string;
  className?: string;
}

const MarkdownContent = ({ content, className }: MarkdownContentProps) => (
  <div className={`markdown-content${className ? ` ${className}` : ''}`}>
    <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
  </div>
);

export default MarkdownContent;
